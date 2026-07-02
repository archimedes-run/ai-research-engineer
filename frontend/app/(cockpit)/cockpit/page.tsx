'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { apiUrl } from '@/lib/api'
import { MODES, DOMAINS, modeToPayload, type Mode, type Domain } from '@/lib/options'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Session {
  session_id: string
  display_id: string
  topic: string
  status: 'running' | 'completed' | 'error' | 'interrupted'
  agent_type: string
  research_mode: string
  started_at: string
  completed_at?: string
  duration?: number
}

// ---------------------------------------------------------------------------
// Auth helper
// SSE (EventSource) cannot send headers; v0 assumes the /stream endpoint is
// open (no ARCHIMEDES_API_TOKEN set). For regular fetch calls we include the
// token when available. Phase D will add signed-ticket auth for SSE.
// ---------------------------------------------------------------------------
function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
function StatusBadge({ status }: { status: Session['status'] }) {
  const map: Record<Session['status'], { label: string; color: string; dot: string }> = {
    running: { label: 'running', color: '#E5A44E', dot: 'animate-pulse' },
    completed: { label: 'done', color: '#5DC47A', dot: '' },
    error: { label: 'error', color: '#E05240', dot: '' },
    interrupted: { label: 'stopped', color: '#7A6A5F', dot: '' },
  }
  const s = map[status] ?? { label: status, color: '#7A6A5F', dot: '' }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded-full border"
      style={{ borderColor: `${s.color}40`, color: s.color, background: `${s.color}10` }}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} style={{ background: s.color }} />
      {s.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Relative time helper
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

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CockpitPage() {
  const router = useRouter()
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<Mode>('novel')
  const [domain, setDomain] = useState<Domain>('aiml')
  const [launching, setLaunching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)

  // Fetch session list on mount and poll while any session is running
  useEffect(() => {
    let cancelled = false

    async function fetchSessions() {
      try {
        const res = await fetch(apiUrl('/api/sessions'), { headers: apiHeaders() })
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setSessions(Array.isArray(data) ? data : [])
      } catch {
        // ignore — network may not be up in pure static preview
      } finally {
        if (!cancelled) setLoadingSessions(false)
      }
    }

    fetchSessions()

    // Poll every 8 seconds while any run is active
    const id = setInterval(async () => {
      const res = await fetch(apiUrl('/api/sessions'), { headers: apiHeaders() }).catch(() => null)
      if (!res?.ok || cancelled) return
      const data = await res.json()
      if (!cancelled) setSessions(Array.isArray(data) ? data : [])
    }, 8000)

    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  async function handleLaunch(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim()) return
    setLaunching(true)
    setError(null)

    try {
      const payload = {
        topic: topic.trim(),
        domain,
        ...modeToPayload(mode),
      }
      const res = await fetch(apiUrl('/api/sessions'), {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const body = await res.text()
        throw new Error(`${res.status}: ${body}`)
      }
      const { session_id } = await res.json()
      router.push(`/cockpit/${session_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Launch failed')
      setLaunching(false)
    }
  }

  const inputStyle = {
    background: '#1A1714',
    border: '1px solid rgba(240, 230, 219, 0.10)',
    color: '#F0E6DB',
    borderRadius: 6,
    outline: 'none',
    width: '100%',
    fontFamily: 'var(--font-outfit), system-ui, sans-serif',
  } as React.CSSProperties

  const labelStyle = {
    display: 'block',
    fontSize: 11,
    letterSpacing: '0.1em',
    textTransform: 'uppercase' as const,
    color: '#7A6A5F',
    marginBottom: 6,
    fontFamily: 'var(--font-outfit), system-ui, sans-serif',
  }

  return (
    <div className="min-h-screen" style={{ fontFamily: 'var(--font-outfit), system-ui, sans-serif' }}>
      {/* Top bar */}
      <header
        className="flex items-center justify-between px-6 h-14 border-b"
        style={{ borderColor: 'rgba(240, 230, 219, 0.08)' }}
      >
        <Link
          href="/"
          className="text-sm font-mono tracking-widest uppercase hover:opacity-70 transition-opacity"
          style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
        >
          ← archimedes
        </Link>
        <span
          className="text-xs tracking-widest uppercase"
          style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
        >
          cockpit
        </span>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-10">
        {/* Launcher */}
        <section>
          <h1
            className="text-2xl font-bold mb-6"
            style={{ fontFamily: 'var(--font-syne), system-ui, sans-serif', color: '#F0E6DB' }}
          >
            New Run
          </h1>

          <form
            onSubmit={handleLaunch}
            className="rounded-xl border p-6 space-y-5"
            style={{ background: '#161412', borderColor: 'rgba(240, 230, 219, 0.08)' }}
          >
            {/* Topic */}
            <div>
              <label style={labelStyle}>Research Topic</label>
              <textarea
                rows={3}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Describe the research task or question…"
                required
                style={{
                  ...inputStyle,
                  padding: '10px 12px',
                  resize: 'vertical',
                  fontSize: 14,
                  lineHeight: 1.5,
                }}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Mode */}
              <div>
                <label style={labelStyle}>Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as Mode)}
                  style={{ ...inputStyle, padding: '8px 12px', fontSize: 14 }}
                >
                  {MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Domain */}
              <div>
                <label style={labelStyle}>Domain</label>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value as Domain)}
                  style={{ ...inputStyle, padding: '8px 12px', fontSize: 14 }}
                >
                  {DOMAINS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Mode description */}
            <p style={{ fontSize: 12, color: '#7A6A5F' }}>
              {MODES.find((m) => m.value === mode)?.description}
            </p>

            {error && (
              <div
                className="text-sm px-3 py-2 rounded"
                style={{ background: '#E0524020', color: '#E05240', border: '1px solid #E0524040' }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={launching || !topic.trim()}
              className="px-6 py-2.5 rounded-lg font-medium text-sm transition-all disabled:opacity-40"
              style={{
                background: launching || !topic.trim() ? '#2A2420' : '#E05240',
                color: '#FFFFFF',
                fontFamily: 'var(--font-syne), system-ui, sans-serif',
                letterSpacing: '0.04em',
                cursor: launching || !topic.trim() ? 'not-allowed' : 'pointer',
              }}
            >
              {launching ? 'Launching…' : 'Run →'}
            </button>
          </form>
        </section>

        {/* Run list */}
        <section>
          <h2
            className="text-sm font-semibold tracking-widest uppercase mb-4"
            style={{ fontFamily: 'var(--font-syne), system-ui, sans-serif', color: '#7A6A5F' }}
          >
            Recent Runs
          </h2>

          {loadingSessions ? (
            <div style={{ color: '#7A6A5F', fontSize: 13 }}>Loading…</div>
          ) : sessions.length === 0 ? (
            <div
              className="rounded-xl border p-8 text-center text-sm"
              style={{ borderColor: 'rgba(240, 230, 219, 0.08)', color: '#7A6A5F' }}
            >
              No runs yet. Launch one above.
            </div>
          ) : (
            <div
              className="rounded-xl border overflow-hidden divide-y"
              style={{ borderColor: 'rgba(240, 230, 219, 0.08)' }}
            >
              {sessions.map((s) => (
                <Link
                  key={s.session_id}
                  href={`/cockpit/${s.session_id}`}
                  className="flex items-start justify-between px-5 py-4 transition-colors group"
                  style={{ background: '#161412' }}
                  onMouseEnter={(e) => {
                    ;(e.currentTarget as HTMLElement).style.background = '#1E1A17'
                  }}
                  onMouseLeave={(e) => {
                    ;(e.currentTarget as HTMLElement).style.background = '#161412'
                  }}
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="text-xs font-mono"
                        style={{ color: '#7A6A5F' }}
                      >
                        {s.display_id}
                      </span>
                      <StatusBadge status={s.status} />
                    </div>
                    <p
                      className="text-sm truncate"
                      style={{ color: '#F0E6DB' }}
                    >
                      {s.topic}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: '#7A6A5F' }}>
                      {s.agent_type} · {s.research_mode} · {relTime(s.started_at)}
                    </p>
                  </div>
                  <span className="text-sm shrink-0" style={{ color: '#E05240' }}>
                    →
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
