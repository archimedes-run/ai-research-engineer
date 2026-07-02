import { notFound } from 'next/navigation'
import { cockpitEnabled } from '@/lib/flags'

// All cockpit routes are flag-gated. With NEXT_PUBLIC_ENABLE_COCKPIT unset
// (Vercel production), this layout calls notFound() so no cockpit page is
// reachable and no cockpit link renders in the main nav.
export default function CockpitLayout({
  children,
}: {
  children: React.ReactNode
}) {
  if (!cockpitEnabled()) {
    notFound()
  }

  return (
    // Full-height dark wrapper — isolates cockpit from the marketing site theme.
    // The root layout.tsx body still applies but the warm-black background here
    // covers it completely.
    <div className="min-h-screen" style={{ background: '#0C0A09', color: '#F0E6DB' }}>
      {children}
    </div>
  )
}
