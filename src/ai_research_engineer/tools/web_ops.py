"""
Web operation tools for ADK agents.

Provides HTTP GET functionality with timeout and user-agent configuration.
"""

import contextlib
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import requests


# Private, loopback, link-local, and cloud-metadata address ranges that must
# never be contacted to prevent SSRF attacks.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC-1918 private
    ipaddress.ip_network("172.16.0.0/12"),  # RFC-1918 private
    ipaddress.ip_network("192.168.0.0/16"),  # RFC-1918 private
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("100.64.0.0/10"),  # shared address space (RFC 6598)
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def _is_blocked(host: str) -> bool:
    """Return True if *host* resolves to a blocked (private/metadata) address."""
    try:
        # getaddrinfo handles both A and AAAA records.
        results = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Cannot resolve → treat as safe; the request itself will fail.
        return False

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return True
    return False


def _check_url_for_ssrf(url: str) -> Optional[str]:
    """
    Return an error string if the URL targets a private/metadata address,
    None if it is safe.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return "Invalid URL: could not determine hostname."
    if _is_blocked(host):
        return (
            f"Request to '{host}' is blocked: target resolves to a private, "
            "loopback, link-local, or cloud-metadata address."
        )
    return None


def _resolve_and_validate(host: str):
    """Resolve *host* ONCE and validate its addresses (S0-8, DNS TOCTOU fix).

    Returns ``(addrinfo_results, error)``:
      * ``(results, None)`` — safe; ``results`` are the validated addresses,
      * ``(None, error_str)`` — a resolved address is private/metadata (blocked),
      * ``(None, None)`` — unresolvable; let the request fail naturally.

    The returned ``results`` are pinned onto the actual connection via
    ``_pinned_resolution`` so the address that is validated is the same address
    that is connected to — closing the check-then-connect race.
    """
    try:
        results = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None, None

    for _family, _type, _proto, _canonname, sockaddr in results:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return None, (
                    f"Request to '{host}' is blocked: target resolves to a private, "
                    "loopback, link-local, or cloud-metadata address."
                )
    return results, None


@contextlib.contextmanager
def _pinned_resolution(host: str, validated_results):
    """Force ``socket.getaddrinfo`` to return only the pre-validated addresses for
    *host* during the request (single-resolution).

    This guarantees the connection uses the exact address we validated, so a DNS
    entry that flips to a private IP between the SSRF check and the connect
    cannot be reached. The requested port from the caller is preserved.
    """
    real_getaddrinfo = socket.getaddrinfo

    def _patched(a_host, a_port=None, *args, **kwargs):
        if a_host != host:
            return real_getaddrinfo(a_host, a_port, *args, **kwargs)
        rebuilt = []
        for family, socktype, proto, canon, sockaddr in validated_results:
            ip = sockaddr[0]
            if family == socket.AF_INET6:
                flowinfo = sockaddr[2] if len(sockaddr) > 2 else 0
                scope_id = sockaddr[3] if len(sockaddr) > 3 else 0
                new_sockaddr = (ip, a_port or 0, flowinfo, scope_id)
            else:
                new_sockaddr = (ip, a_port or 0)
            rebuilt.append((family, socktype, proto, canon, new_sockaddr))
        return rebuilt

    socket.getaddrinfo = _patched
    try:
        yield
    finally:
        socket.getaddrinfo = real_getaddrinfo


def _truncate_content(content: str, max_content_length: int) -> str:
    """
    Truncate content to maximum length and add warning if truncated.

    Parameters
    ----------
    content : str
        The content to potentially truncate
    max_content_length : int
        Maximum allowed length in characters

    Returns
    -------
    str
        Original content if under limit, or truncated content with warning message
    """
    if len(content) <= max_content_length:
        return content

    original_length = len(content)
    truncated = content[:max_content_length]
    warning = (
        f"\n\n[Content truncated at {max_content_length:,} characters. Original length: {original_length:,} characters]"
    )
    return truncated + warning


def _extract_readable_markdown(text: str) -> Optional[str]:
    """Extract the readable article as markdown (S1-3, via trafilatura).

    Returns ``None`` when the input isn't HTML or nothing readable is found, so
    the caller can fall back to the raw text.
    """
    if "<" not in text:  # not HTML — nothing to extract
        return None
    try:
        import trafilatura

        return trafilatura.extract(
            text,
            output_format="markdown",
            include_tables=True,
            include_formatting=True,
            favor_recall=True,
        )
    except Exception:
        return None


def _paginate(content: str, offset: int, max_content_length: int) -> str:
    """Return the ``[offset : offset+max_content_length]`` window, with a
    continuation hint when more content remains (S1-3 pagination)."""
    total = len(content)
    if offset < 0:
        offset = 0
    if offset >= total:
        return f"[No more content: offset {offset:,} is past the end ({total:,} characters).]"
    window = content[offset : offset + max_content_length]
    next_offset = offset + max_content_length
    if next_offset < total:
        window += (
            f"\n\n[More content available: {total:,} characters total. "
            f"Call again with offset={next_offset} to continue.]"
        )
    return window


def fetch_url(
    url: str,
    timeout: int = 30,
    user_agent: Optional[str] = None,
    max_content_length: int = 25000,
    offset: int = 0,
) -> str:
    """
    Fetch content from a URL using HTTP GET.

    Requests to private, loopback, link-local, and cloud-metadata addresses
    (including AWS/GCP/Azure metadata endpoints) are blocked to prevent SSRF.
    Redirects are followed manually so that each hop is validated before
    the request is sent.

    Parameters
    ----------
    url : str
        The URL to fetch
    timeout : int, optional
        Request timeout in seconds, default 30
    user_agent : str, optional
        Custom User-Agent header, default None (uses requests default)
    max_content_length : int, optional
        Maximum content length in characters before truncation, default 10000

        **WARNING: Do not modify max_content_length unless absolutely necessary.
        The default 10,000 character limit prevents token overflow.**

    Returns
    -------
    str
        Response content or error message

    Notes
    -----
    - Only HTTP and HTTPS protocols are supported
    - Each redirect hop is SSRF-checked before following
    - Returns text content with automatic encoding detection
    - Returns error message for failed requests
    - Content exceeding max_content_length will be truncated with a warning message

    Examples
    --------
    >>> content = fetch_url("https://example.com")
    >>> print(content[:100])  # First 100 characters
    """
    try:
        # Validate URL scheme
        if not url.startswith(("http://", "https://")):
            return "Error: Only HTTP and HTTPS URLs are supported"

        headers = {}
        if user_agent is not None:
            headers["User-Agent"] = user_agent

        # Disable automatic redirects so we can validate each hop.
        current_url = url
        max_redirects = 10
        for _ in range(max_redirects + 1):
            host = urlparse(current_url).hostname
            if not host:
                return "Error: Invalid URL: could not determine hostname."

            # Resolve the host ONCE, validate it, and pin that resolution onto
            # the connection so the validated address is the one we connect to.
            validated, ssrf_error = _resolve_and_validate(host)
            if ssrf_error:
                return f"Error: {ssrf_error}"

            pin = _pinned_resolution(host, validated) if validated else contextlib.nullcontext()
            with pin:
                response = requests.get(
                    current_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=False,
                )

            if response.is_redirect:
                location = response.headers.get("Location", "")
                if not location:
                    return "Error: Redirect with no Location header"
                # Resolve relative redirects
                if not location.startswith(("http://", "https://")):
                    parsed = urlparse(current_url)
                    location = f"{parsed.scheme}://{parsed.netloc}{location}"
                ssrf_error = _check_url_for_ssrf(location)
                if ssrf_error:
                    return f"Error: Redirect blocked — {ssrf_error}"
                current_url = location
                continue

            response.raise_for_status()
            # Extract readable markdown (fall back to the raw body), then page it.
            content = _extract_readable_markdown(response.text) or response.text
            return _paginate(content, offset, max_content_length)

        return "Error: Too many redirects"

    except requests.exceptions.Timeout:
        return f"Error: Request timed out after {timeout} seconds"
    except requests.exceptions.ConnectionError:
        return f"Error: Failed to connect to {url}"
    except requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code} - {e.response.reason}"
    except requests.exceptions.RequestException as e:
        return f"Error: Request failed - {e}"
    except Exception as e:
        return f"Error fetching URL: {e}"
