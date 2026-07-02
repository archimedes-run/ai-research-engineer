// Cockpit / app UI is dark until this is explicitly enabled.
// Unset (Vercel production) -> false -> new routes notFound(), no nav links.
// Set "true" on Vercel Preview / local to develop and demo the cockpit.
export function cockpitEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_COCKPIT === "true";
}
