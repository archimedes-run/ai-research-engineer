"""
Web operation tools for ADK agents.

Provides HTTP GET functionality with timeout and user-agent configuration.
"""

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


def fetch_url(
    url: str,
    timeout: int = 30,
    user_agent: Optional[str] = None,
    max_content_length: int = 10000,
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

        # SSRF check on the initial URL
        ssrf_error = _check_url_for_ssrf(url)
        if ssrf_error:
            return f"Error: {ssrf_error}"

        headers = {}
        if user_agent is not None:
            headers["User-Agent"] = user_agent

        # Disable automatic redirects so we can validate each hop.
        current_url = url
        max_redirects = 10
        for _ in range(max_redirects + 1):
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
            content = _truncate_content(response.text, max_content_length)
            return content

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
