'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowRight, ChevronDown, Eye, FlaskConical, Globe, Zap } from 'lucide-react'
import { apiUrl } from '@/lib/api'
import { MODES, DOMAINS, modeToPayload, type Mode, type Domain } from '@/lib/options'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Session {
  session_id: string
  display_id: string
  topic: string
  status: 'running' | 'completed' | 'error' | 'interrupted' | 'failed'
  agent_type: string
  research_mode: string
  started_at: string
  completed_at?: string
  duration?: number
}

function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

// ---------------------------------------------------------------------------
// Design tokens — light beige-peach, minimal
// ---------------------------------------------------------------------------
const C = {
  bg: '#F5EFE8',          // warm beige-peach
  surface: '#FDFAF7',     // slightly lighter for cards/inputs
  border: '#E2D8CF',
  border2: '#CEC4BA',
  text: '#2E2520',
  muted: '#8A7A71',
  brand: '#E05240',
  green: '#1E8A3E',
  amber: '#B07010',
  blue: '#2563EB',
  sidebar: '#EDE5DC',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function StatusDot({ status }: { status: Session['status'] }) {
  const map: Record<string, string> = {
    running: C.amber,
    completed: C.green,
    error: C.brand,
    failed: C.brand,
    interrupted: C.muted,
  }
  const color = map[status] ?? C.muted
  return (
    <span
      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1 ${status === 'running' ? 'animate-pulse' : ''}`}
      style={{ background: color }}
    />
  )
}

// ---------------------------------------------------------------------------
// Generic dropdown
// ---------------------------------------------------------------------------
function Dropdown<T extends string>({
  icon,
  label,
  options,
  value,
  onChange,
}: {
  icon: React.ReactNode
  label: string
  options: readonly { value: T; label: string; description?: string }[]
  value: T
  onChange: (v: T) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const current = options.find(o => o.value === value)

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-all"
        style={{
          borderColor: open ? C.brand : C.border,
          background: open ? `${C.brand}08` : C.surface,
          color: open ? C.brand : C.muted,
        }}
        title={`${label}: ${current?.label}`}
      >
        <span className="w-3.5 h-3.5" style={{ color: open ? C.brand : C.muted }}>{icon}</span>
        <span style={{ fontFamily: 'var(--font-outfit)' }}>{current?.label}</span>
        <ChevronDown className="w-3 h-3 opacity-60" />
      </button>

      {open && (
        <div
          className="absolute bottom-full mb-2 left-0 rounded-xl shadow-lg border py-1 z-50"
          style={{ background: C.surface, borderColor: C.border, minWidth: 200 }}
        >
          {options.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { onChange(opt.value); setOpen(false) }}
              className="w-full text-left px-4 py-2.5 flex flex-col gap-0.5 transition-colors"
              style={{
                background: opt.value === value ? `${C.brand}08` : 'transparent',
                color: opt.value === value ? C.brand : C.text,
              }}
              onMouseEnter={e => { if (opt.value !== value) (e.currentTarget as HTMLElement).style.background = `${C.border}60` }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = opt.value === value ? `${C.brand}08` : 'transparent' }}
            >
              <span className="text-xs font-medium" style={{ fontFamily: 'var(--font-outfit)' }}>{opt.label}</span>
              {opt.description && (
                <span className="text-xs leading-snug" style={{ color: C.muted, fontFamily: 'var(--font-outfit)' }}>{opt.description}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Launcher page
// ---------------------------------------------------------------------------
export default function CockpitPage() {
  const router = useRouter()
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<Mode>('novel')
  const [domain, setDomain] = useState<Domain>('aiml')
  const [hitlEnabled, setHitlEnabled] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])

  // ---------------------------------------------------------------------------
  // Poll sessions
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(apiUrl('/api/sessions'), { headers: apiHeaders() })
        if (!res.ok || cancelled) return
        const data = await res.json()
        if (!cancelled) setSessions(Array.isArray(data) ? data : [])
      } catch { /* ignore */ }
    }
    load()
    const id = setInterval(load, 8000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // ---------------------------------------------------------------------------
  // Launch
  // ---------------------------------------------------------------------------
  async function handleLaunch(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim() || launching) return
    setLaunching(true)
    setError(null)
    try {
      const res = await fetch(apiUrl('/api/sessions'), {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ topic: topic.trim(), domain, ...modeToPayload(mode), hitl_enabled: hitlEnabled }),
      })
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
      const { session_id } = await res.json()
      router.push(`/cockpit/${session_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Launch failed')
      setLaunching(false)
    }
  }

  const canLaunch = topic.trim().length > 0 && !launching

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: C.bg, color: C.text, fontFamily: 'var(--font-outfit), system-ui, sans-serif' }}
    >
      {/* ── Left sidebar ────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col border-r overflow-y-auto flex-shrink-0"
        style={{ width: 248, background: C.sidebar, borderColor: C.border }}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b" style={{ borderColor: C.border }}>
          <Link
            href="/"
            className="text-sm font-bold tracking-[0.14em] uppercase transition-opacity hover:opacity-70"
            style={{ color: C.text, fontFamily: 'var(--font-syne)' }}
          >
            archimedes
          </Link>
        </div>

        {/* New run button */}
        <div className="px-4 py-3 border-b" style={{ borderColor: C.border }}>
          <button
            onClick={() => { setTopic(''); setError(null) }}
            className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all"
            style={{ background: C.brand, color: '#fff', fontFamily: 'var(--font-syne)' }}
          >
            <span className="text-base leading-none font-light">+</span>
            New Run
          </button>
        </div>

        {/* Recent runs */}
        <div className="flex-1 px-3 py-3 overflow-y-auto">
          <div
            className="text-xs uppercase tracking-widest mb-2 px-2"
            style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}
          >
            Recent
          </div>
          {sessions.length === 0 ? (
            <p className="px-2 text-xs" style={{ color: C.muted }}>No runs yet</p>
          ) : (
            <div className="space-y-0.5">
              {sessions.map((s) => (
                <Link
                  key={s.session_id}
                  href={`/cockpit/${s.session_id}`}
                  className="flex items-start gap-2 px-2 py-2 rounded-lg transition-colors"
                  style={{ color: C.text }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = C.border)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <StatusDot status={s.status} />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-mono truncate" style={{ color: C.muted }}>
                      {s.display_id}
                    </div>
                    <div className="text-xs truncate mt-0.5" style={{ color: C.text }}>
                      {s.topic}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: C.muted }}>
                      {relTime(s.started_at)}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* ── Main — centered launcher ─────────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 overflow-y-auto">
        <div className="w-full max-w-xl">
          {/* Heading */}
          <div className="text-center mb-8">
            <h1
              className="text-2xl font-bold mb-2"
              style={{ fontFamily: 'var(--font-syne)', color: C.text }}
            >
              What should Archimedes research?
            </h1>
            <p className="text-sm" style={{ color: C.muted }}>
              Describe a hypothesis, question, or topic.
            </p>
          </div>

          {/* Input card */}
          <form onSubmit={handleLaunch}>
            <div
              className="rounded-2xl border shadow-sm overflow-hidden"
              style={{ borderColor: C.border, background: C.surface }}
            >
              <textarea
                rows={5}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Explore whether sparse attention mechanisms can match dense transformers on long-context reasoning tasks…"
                className="w-full px-5 pt-5 pb-3 text-sm leading-relaxed resize-none outline-none"
                style={{
                  fontFamily: 'var(--font-outfit)',
                  color: C.text,
                  background: 'transparent',
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleLaunch(e as unknown as React.FormEvent)
                }}
              />

              {/* Bottom bar */}
              <div
                className="flex items-center gap-2 px-4 pb-4 pt-2 border-t"
                style={{ borderColor: C.border }}
              >
                {/* Mode dropdown */}
                <Dropdown<Mode>
                  icon={<FlaskConical className="w-3.5 h-3.5" />}
                  label="Mode"
                  options={MODES}
                  value={mode}
                  onChange={setMode}
                />

                {/* Domain dropdown */}
                <Dropdown<Domain>
                  icon={<Globe className="w-3.5 h-3.5" />}
                  label="Domain"
                  options={DOMAINS}
                  value={domain}
                  onChange={setDomain}
                />

                {/* Supervised / Autonomous toggle */}
                <button
                  type="button"
                  onClick={() => setHitlEnabled(v => !v)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs transition-all"
                  style={{
                    borderColor: hitlEnabled ? C.blue : C.border,
                    background: hitlEnabled ? `${C.blue}08` : C.surface,
                    color: hitlEnabled ? C.blue : C.muted,
                    fontFamily: 'var(--font-outfit)',
                  }}
                  title={hitlEnabled ? 'Supervised: pauses for your review at key gates' : 'Autonomous: runs end-to-end without interruption'}
                >
                  {hitlEnabled
                    ? <Eye className="w-3.5 h-3.5" />
                    : <Zap className="w-3.5 h-3.5" />}
                  {hitlEnabled ? 'Supervised' : 'Autonomous'}
                </button>

                {/* Submit — arrow icon only */}
                <button
                  type="submit"
                  disabled={!canLaunch}
                  className="ml-auto flex items-center justify-center w-9 h-9 rounded-xl transition-all flex-shrink-0"
                  style={{
                    background: canLaunch ? C.brand : C.border,
                    color: canLaunch ? '#fff' : C.muted,
                    cursor: canLaunch ? 'pointer' : 'not-allowed',
                  }}
                  title="Run (⌘↵)"
                >
                  {launching
                    ? <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    : <ArrowRight className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div
                className="mt-3 text-sm px-4 py-2 rounded-lg border"
                style={{ background: `${C.brand}08`, borderColor: `${C.brand}30`, color: C.brand }}
              >
                {error}
              </div>
            )}
          </form>

          <p className="text-center text-xs mt-3" style={{ color: C.muted }}>
            Press ⌘↵ to run
          </p>
        </div>
      </main>
    </div>
  )
}
