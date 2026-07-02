// Base URL for the Archimedes backend API.
// Local dev & Docker: leave NEXT_PUBLIC_API_BASE unset -> same-origin "/api/*"
//   is proxied to the gateway by nginx.
// Vercel preview: set NEXT_PUBLIC_API_BASE to your tunnel origin (e.g. cloudflared).
// Vercel production: unset (cockpit is flag-gated off until the backend is hosted).
export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE ?? "";
}

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${apiBase()}${p}`; // callers use apiUrl("/api/sessions"), etc.
}
