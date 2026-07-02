'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import Link from 'next/link'
import { use } from 'react'
import { apiUrl } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types — mirror server/events.py + server/app.py response shapes
// ---------------------------------------------------------------------------

interface BaseStreamEvent {
  type: string
  timestamp?: string
  seq?: number
}

interface MessageEvent extends BaseStreamEvent {
  type: 'message'
  content: string
  author: string
  is_thought: boolean
  is_partial: boolean
}

interface FunctionCallEvent extends BaseStreamEvent {
  type: 'function_call'
  name: string
  arguments: Record<string, unknown>
  author: string
}

interface FunctionResponseEvent extends BaseStreamEvent {
  type: 'function_response'
  name: string
  response: unknown
  author: string
}

interface UsageEvent extends BaseStreamEvent {
  type: 'usage'
  model?: string
  usage: {
    input_tokens: number
    cached_input_tokens: number
    output_tokens: number
  }
}

interface CompletedEvent extends BaseStreamEvent {
  type: 'completed'
  session_id?: string
  duration?: number
  files_created?: string[]
  files_count?: number
}

interface ErrorEvent extends BaseStreamEvent {
  type: 'error'
  content: string
}

type StreamEvent =
  | MessageEvent
  | FunctionCallEvent
  | FunctionResponseEvent
  | UsageEvent
  | CompletedEvent
  | ErrorEvent
  | BaseStreamEvent

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

interface UsageTotals {
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  cost_usd: number
}

interface UsageByModel {
  model: string | null
  engine: string | null
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  cost_usd: number
}

interface UsageData {
  totals: UsageTotals
  by_model: UsageByModel[]
}

interface TreeStats {
  total_nodes: number
  by_type: Record<string, number>
  by_status: Record<string, number>
}

interface TreeGap {
  node_id?: string
  label?: string
  content?: string
  [k: string]: unknown
}

interface TreeData {
  stats: TreeStats
  gaps: TreeGap[]
  context?: string
}

// ---------------------------------------------------------------------------
// Auth
// SSE (EventSource) cannot carry custom headers. v0 assumes the /stream
// endpoint requires no auth token (ARCHIMEDES_API_TOKEN unset on backend).
// Phase D will add signed-ticket auth so EventSource can authenticate.
// ---------------------------------------------------------------------------
function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token } : {}
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function fmtDuration(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  const rem = Math.floor(s % 60)
  return `${m}m ${rem}s`
}

function fmtCost(usd: number): string {
  if (usd === 0) return '$0.00'
  if (usd < 0.0001) return '<$0.0001'
  return `$${usd.toFixed(4)}`
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function truncate(s: string, max = 120): string {
  return s.length <= max ? s : s.slice(0, max) + '…'
}

function safeJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
type Status = Session['status'] | 'connecting'

function StatusBadge({ status }: { status: Status }) {
  const map: Record<Status, { label: string; color: string; pulse: boolean }> = {
    connecting: { label: 'connecting', color: '#7A6A5F', pulse: true },
    running: { label: 'running', color: '#E5A44E', pulse: true },
    completed: { label: 'completed', color: '#5DC47A', pulse: false },
    error: { label: 'error', color: '#E05240', pulse: false },
    interrupted: { label: 'stopped', color: '#7A6A5F', pulse: false },
  }
  const s = map[status] ?? { label: status, color: '#7A6A5F', pulse: false }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded-full border"
      style={{ borderColor: `${s.color}40`, color: s.color, background: `${s.color}10` }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full${s.pulse ? ' animate-pulse' : ''}`}
        style={{ background: s.color }}
      />
      {s.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Event row components
// ---------------------------------------------------------------------------

function MessageRow({ event }: { event: MessageEvent }) {
  const [expanded, setExpanded] = useState(!event.is_thought)

  if (event.is_thought) {
    return (
      <div className="py-1">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-2 text-xs w-full text-left group"
          style={{ color: '#7A6A5F' }}
        >
          <span style={{ fontFamily: 'var(--font-fira-code), monospace' }}>
            {expanded ? '▾' : '▸'}
          </span>
          <span className="opacity-60 group-hover:opacity-100 transition-opacity">
            reasoning ({event.author})
          </span>
        </button>
        {expanded && (
          <div
            className="mt-1.5 ml-4 text-xs leading-relaxed px-3 py-2 rounded border-l-2 whitespace-pre-wrap"
            style={{
              color: '#7A6A5F',
              background: '#1A1714',
              borderColor: '#7A6A5F40',
              fontFamily: 'var(--font-outfit), system-ui, sans-serif',
            }}
          >
            {event.content}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="py-1.5">
      <div className="flex items-baseline gap-2 mb-0.5">
        <span
          className="text-xs font-mono uppercase tracking-wide"
          style={{ color: '#E05240' }}
        >
          {event.author}
        </span>
        {event.timestamp && (
          <span className="text-xs" style={{ color: '#7A6A5F40' }}>
            {event.timestamp}
          </span>
        )}
      </div>
      <p
        className="text-sm leading-relaxed whitespace-pre-wrap"
        style={{ color: '#EDE3D9', fontFamily: 'var(--font-outfit), system-ui, sans-serif' }}
      >
        {event.content}
      </p>
    </div>
  )
}

function ToolRow({ call, response }: { call: FunctionCallEvent; response?: FunctionResponseEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasArgs = Object.keys(call.arguments ?? {}).length > 0

  return (
    <div className="py-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs w-full text-left"
        style={{ color: '#8A7A6E' }}
      >
        <span style={{ fontFamily: 'var(--font-fira-code), monospace' }}>
          {expanded ? '▾' : '▸'}
        </span>
        <span
          className="px-2 py-0.5 rounded text-xs font-mono"
          style={{ background: '#1E1A17', color: '#E5A44E', border: '1px solid #E5A44E30' }}
        >
          ⚙ {call.name}
        </span>
        {!expanded && hasArgs && (
          <span style={{ color: '#7A6A5F' }} className="truncate max-w-[300px] font-mono text-xs">
            {truncate(safeJson(call.arguments))}
          </span>
        )}
        {response && !expanded && (
          <span className="text-xs" style={{ color: '#5DC47A40' }}>✓</span>
        )}
      </button>

      {expanded && (
        <div className="mt-2 ml-4 space-y-2">
          {hasArgs && (
            <div>
              <div className="text-xs mb-1" style={{ color: '#7A6A5F' }}>args</div>
              <pre
                className="text-xs p-3 rounded overflow-x-auto"
                style={{
                  background: '#1A1714',
                  color: '#E5A44E',
                  fontFamily: 'var(--font-fira-code), monospace',
                  maxHeight: 200,
                  overflowY: 'auto',
                }}
              >
                {safeJson(call.arguments)}
              </pre>
            </div>
          )}
          {response && (
            <div>
              <div className="text-xs mb-1" style={{ color: '#7A6A5F' }}>response</div>
              <pre
                className="text-xs p-3 rounded overflow-x-auto"
                style={{
                  background: '#1A1714',
                  color: '#8A9F7E',
                  fontFamily: 'var(--font-fira-code), monospace',
                  maxHeight: 200,
                  overflowY: 'auto',
                }}
              >
                {truncate(safeJson(response.response), 2000)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function UnknownRow({ event }: { event: BaseStreamEvent }) {
  return (
    <div
      className="py-1 px-2 text-xs font-mono rounded border"
      style={{ color: '#7A6A5F', borderColor: 'rgba(240, 230, 219, 0.05)', background: '#1A1714' }}
    >
      [{event.type}]
      {event.timestamp && ` ${event.timestamp}`}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Cost meter
// ---------------------------------------------------------------------------
function CostMeter({ usage, liveUsage }: { usage: UsageData | null; liveUsage: UsageTotals }) {
  const totals = usage?.totals ?? liveUsage
  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: '#161412', borderColor: 'rgba(240, 230, 219, 0.08)' }}
    >
      <h3
        className="text-xs tracking-widest uppercase font-semibold"
        style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
      >
        Cost
      </h3>
      <div className="flex items-baseline gap-2">
        <span
          className="text-2xl font-mono font-bold"
          style={{ color: '#E05240', fontFamily: 'var(--font-fira-code), monospace' }}
        >
          {fmtCost(totals.cost_usd)}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs" style={{ fontFamily: 'var(--font-fira-code), monospace' }}>
        <div>
          <div style={{ color: '#7A6A5F' }}>input</div>
          <div style={{ color: '#EDE3D9' }}>{fmtTokens(totals.input_tokens)}</div>
        </div>
        <div>
          <div style={{ color: '#7A6A5F' }}>cached</div>
          <div style={{ color: '#EDE3D9' }}>{fmtTokens(totals.cached_input_tokens)}</div>
        </div>
        <div>
          <div style={{ color: '#7A6A5F' }}>output</div>
          <div style={{ color: '#EDE3D9' }}>{fmtTokens(totals.output_tokens)}</div>
        </div>
        <div>
          <div style={{ color: '#7A6A5F' }}>calls</div>
          <div style={{ color: '#EDE3D9' }}>{usage?.by_model?.length ?? '—'}</div>
        </div>
      </div>
      {usage?.by_model && usage.by_model.length > 0 && (
        <div className="pt-2 border-t space-y-1" style={{ borderColor: 'rgba(240, 230, 219, 0.06)' }}>
          {usage.by_model.map((row, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="font-mono truncate max-w-[120px]" style={{ color: '#8A7A6E' }}>
                {row.model ?? row.engine ?? 'unknown'}
              </span>
              <span className="font-mono" style={{ color: '#E05240' }}>
                {fmtCost(row.cost_usd)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tree inspector
// ---------------------------------------------------------------------------
function TreeInspector({ tree }: { tree: TreeData | null }) {
  if (!tree) {
    return (
      <div
        className="rounded-xl border p-4"
        style={{ background: '#161412', borderColor: 'rgba(240, 230, 219, 0.08)' }}
      >
        <h3
          className="text-xs tracking-widest uppercase font-semibold mb-2"
          style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
        >
          Research Tree
        </h3>
        <p className="text-xs" style={{ color: '#7A6A5F' }}>
          Tree will appear once the agent starts building nodes.
        </p>
      </div>
    )
  }

  const { stats, gaps } = tree
  return (
    <div
      className="rounded-xl border p-4 space-y-3"
      style={{ background: '#161412', borderColor: 'rgba(240, 230, 219, 0.08)' }}
    >
      <h3
        className="text-xs tracking-widest uppercase font-semibold"
        style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
      >
        Research Tree
      </h3>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div style={{ color: '#7A6A5F' }}>nodes</div>
          <div
            className="text-lg font-mono font-bold"
            style={{ color: '#5DC47A', fontFamily: 'var(--font-fira-code), monospace' }}
          >
            {stats.total_nodes}
          </div>
        </div>
        <div>
          <div style={{ color: '#7A6A5F' }}>gaps</div>
          <div
            className="text-lg font-mono font-bold"
            style={{
              color: gaps.length > 0 ? '#E5A44E' : '#5DC47A',
              fontFamily: 'var(--font-fira-code), monospace',
            }}
          >
            {gaps.length}
          </div>
        </div>
      </div>

      {/* By type */}
      {Object.entries(stats.by_type ?? {}).length > 0 && (
        <div className="space-y-1">
          {Object.entries(stats.by_type).map(([type, count]) => (
            <div key={type} className="flex items-center justify-between text-xs">
              <span className="font-mono" style={{ color: '#8A7A6E' }}>
                {type}
              </span>
              <span className="font-mono" style={{ color: '#EDE3D9' }}>
                {count}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Gaps */}
      {gaps.length > 0 && (
        <div className="pt-2 border-t space-y-2" style={{ borderColor: 'rgba(240, 230, 219, 0.06)' }}>
          <div className="text-xs" style={{ color: '#7A6A5F' }}>
            Open questions / unsupported claims
          </div>
          {gaps.slice(0, 5).map((gap, i) => (
            <div
              key={i}
              className="text-xs px-2 py-1.5 rounded border"
              style={{
                color: '#E5A44E',
                background: '#E5A44E08',
                borderColor: '#E5A44E20',
                fontFamily: 'var(--font-outfit), system-ui, sans-serif',
              }}
            >
              {truncate(gap.label ?? gap.content ?? JSON.stringify(gap), 80)}
            </div>
          ))}
          {gaps.length > 5 && (
            <div className="text-xs" style={{ color: '#7A6A5F' }}>
              +{gaps.length - 5} more
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main run view
// ---------------------------------------------------------------------------

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params)

  const [session, setSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [connStatus, setConnStatus] = useState<'connecting' | 'live' | 'closed'>('connecting')
  const [usageData, setUsageData] = useState<UsageData | null>(null)
  const [liveUsage, setLiveUsage] = useState<UsageTotals>({
    input_tokens: 0,
    cached_input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
  })
  const [tree, setTree] = useState<TreeData | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [isTerminal, setIsTerminal] = useState(false)

  const feedRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const treeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const elapsedTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startedAtRef = useRef<number>(Date.now())
  // Tracks pairs of function_call + function_response by author+name
  // so we can render them together.
  const pendingCallsRef = useRef<Map<string, FunctionCallEvent>>(new Map())

  // Auto-scroll feed to bottom as events arrive
  const scrollFeed = useCallback(() => {
    const el = feedRef.current
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }, [])

  // Process a single streaming event
  const processEvent = useCallback(
    (raw: BaseStreamEvent) => {
      const type = raw.type

      if (type === 'usage') {
        const ev = raw as UsageEvent
        setLiveUsage((prev) => ({
          input_tokens: prev.input_tokens + (ev.usage?.input_tokens ?? 0),
          cached_input_tokens: prev.cached_input_tokens + (ev.usage?.cached_input_tokens ?? 0),
          output_tokens: prev.output_tokens + (ev.usage?.output_tokens ?? 0),
          cost_usd: prev.cost_usd, // cost_usd comes from the usage endpoint
        }))
        return // don't add usage events to the visible feed
      }

      if (type === 'keepalive') return // silent

      if (type === 'completed' || type === 'error') {
        setIsTerminal(true)
        setConnStatus('closed')
        // Fetch final usage + tree
        fetch(apiUrl(`/api/sessions/${runId}/usage`), { headers: apiHeaders() })
          .then((r) => r.ok ? r.json() : null)
          .then((d) => d && setUsageData(d))
          .catch(() => {})
        fetch(apiUrl(`/api/sessions/${runId}/tree`), { headers: apiHeaders() })
          .then((r) => r.ok ? r.json() : null)
          .then((d) => d && setTree(d))
          .catch(() => {})
        // Stop elapsed timer
        if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current)
      }

      setEvents((prev) => {
        // Deduplicate by seq (events that came via backfill have seq)
        if (raw.seq && prev.some((e) => e.seq === raw.seq)) return prev
        return [...prev, raw]
      })

      setTimeout(scrollFeed, 50)
    },
    [runId, scrollFeed],
  )

  // Fetch session metadata
  useEffect(() => {
    fetch(apiUrl(`/api/sessions/${runId}`), { headers: apiHeaders() })
      .then((r) => r.ok ? r.json() : null)
      .then((s) => {
        if (!s) return
        setSession(s)
        startedAtRef.current = new Date(s.started_at).getTime()
        if (s.duration) setElapsed(s.duration)
        if (s.status !== 'running') setIsTerminal(true)
      })
      .catch(() => {})
  }, [runId])

  // Elapsed timer
  useEffect(() => {
    if (isTerminal) return
    const id = setInterval(() => {
      setElapsed((Date.now() - startedAtRef.current) / 1000)
    }, 500)
    elapsedTimerRef.current = id
    return () => clearInterval(id)
  }, [isTerminal])

  // Main SSE setup: backfill then live-tail
  useEffect(() => {
    let cancelled = false

    async function start() {
      // 1. Backfill via events endpoint
      let maxSeq = 0
      try {
        const res = await fetch(apiUrl(`/api/sessions/${runId}/events?after_seq=0`), {
          headers: apiHeaders(),
        })
        if (res.ok) {
          const backfill: BaseStreamEvent[] = await res.json()
          if (!cancelled) {
            for (const ev of backfill) {
              processEvent(ev)
              if (ev.seq && ev.seq > maxSeq) maxSeq = ev.seq
            }
          }
        }
      } catch {
        // network may be unavailable in purely static preview
      }

      if (cancelled) return

      // 2. Live-tail via EventSource starting after backfill
      // NOTE: EventSource cannot send custom headers. v0 assumes the /stream
      // endpoint is unauthenticated (ARCHIMEDES_API_TOKEN unset on backend).
      // Phase D will introduce signed URL tickets for authenticated SSE.
      const esUrl = apiUrl(`/api/sessions/${runId}/stream?after_seq=${maxSeq}`)
      const es = new EventSource(esUrl)
      esRef.current = es

      es.onopen = () => {
        if (!cancelled) setConnStatus('live')
      }

      es.onmessage = (e) => {
        if (cancelled) return
        try {
          const ev = JSON.parse(e.data) as BaseStreamEvent
          processEvent(ev)
        } catch {
          /* malformed JSON — skip */
        }
      }

      es.onerror = () => {
        if (!cancelled) setConnStatus('closed')
        es.close()
      }
    }

    start()

    return () => {
      cancelled = true
      esRef.current?.close()
      esRef.current = null
    }
  }, [runId, processEvent])

  // Tree polling while run is active
  useEffect(() => {
    if (isTerminal) {
      if (treeTimerRef.current) clearInterval(treeTimerRef.current)
      return
    }

    async function fetchTree() {
      try {
        const res = await fetch(apiUrl(`/api/sessions/${runId}/tree`), { headers: apiHeaders() })
        if (res.ok) {
          const d = await res.json()
          setTree(d)
        }
      } catch {
        /* ignore */
      }
    }

    fetchTree()
    const id = setInterval(fetchTree, 6000)
    treeTimerRef.current = id
    return () => clearInterval(id)
  }, [runId, isTerminal])

  // Usage polling while run is active (supplements live usage events)
  useEffect(() => {
    if (isTerminal) return
    const id = setInterval(async () => {
      try {
        const res = await fetch(apiUrl(`/api/sessions/${runId}/usage`), { headers: apiHeaders() })
        if (res.ok) {
          const d = await res.json()
          setUsageData(d)
        }
      } catch {
        /* ignore */
      }
    }, 10000)
    return () => clearInterval(id)
  }, [runId, isTerminal])

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  function renderFeedItem(event: StreamEvent, i: number) {
    const key = `${event.type}-${event.seq ?? i}`

    switch (event.type) {
      case 'message':
        return <MessageRow key={key} event={event as MessageEvent} />

      case 'function_call': {
        const call = event as FunctionCallEvent
        // Look for the matching response in subsequent events
        const resp = events
          .slice(i + 1)
          .find(
            (e) =>
              e.type === 'function_response' &&
              (e as FunctionResponseEvent).name === call.name,
          ) as FunctionResponseEvent | undefined
        // Only render call here; skip when we encounter the orphan response below
        return <ToolRow key={key} call={call} response={resp} />
      }

      case 'function_response': {
        // Rendered by its matching function_call above; skip standalone
        const prev = events
          .slice(0, i)
          .reverse()
          .find(
            (e) =>
              e.type === 'function_call' &&
              (e as FunctionCallEvent).name === (event as FunctionResponseEvent).name,
          )
        if (prev) return null // already rendered alongside its call
        return <ToolRow key={key} call={{ type: 'function_call', name: (event as FunctionResponseEvent).name, arguments: {}, author: '' }} response={event as FunctionResponseEvent} />
      }

      case 'completed': {
        const ev = event as CompletedEvent
        return (
          <div
            key={key}
            className="py-3 px-4 rounded-lg border text-sm"
            style={{ background: '#5DC47A10', borderColor: '#5DC47A30', color: '#5DC47A' }}
          >
            ✓ Run completed
            {ev.duration != null && ` in ${fmtDuration(ev.duration)}`}
            {ev.files_count != null && ev.files_count > 0 && ` — ${ev.files_count} file${ev.files_count !== 1 ? 's' : ''} created`}
          </div>
        )
      }

      case 'error': {
        const ev = event as ErrorEvent
        return (
          <div
            key={key}
            className="py-3 px-4 rounded-lg border text-sm"
            style={{ background: '#E0524010', borderColor: '#E0524040', color: '#E05240' }}
          >
            ✕ {ev.content || 'An error occurred'}
          </div>
        )
      }

      case 'stage_started':
      case 'stage_completed': {
        const ev = event as BaseStreamEvent & { stage?: string; title?: string }
        return (
          <div
            key={key}
            className="py-1 flex items-center gap-3 text-xs"
            style={{ color: '#7A6A5F' }}
          >
            <span className="h-px flex-1" style={{ background: 'rgba(240, 230, 219, 0.06)' }} />
            <span className="font-mono uppercase tracking-widest">
              {event.type === 'stage_started' ? '▷' : '■'}{' '}
              {(ev.title ?? ev.stage ?? event.type)}
            </span>
            <span className="h-px flex-1" style={{ background: 'rgba(240, 230, 219, 0.06)' }} />
          </div>
        )
      }

      case 'hitl_request': {
        const ev = event as BaseStreamEvent & { question?: string }
        return (
          <div
            key={key}
            className="py-3 px-4 rounded-lg border text-sm"
            style={{
              background: '#E5A44E08',
              borderColor: '#E5A44E40',
              color: '#E5A44E',
              fontFamily: 'var(--font-outfit), system-ui, sans-serif',
            }}
          >
            ⏸ Waiting for input — {ev.question ?? 'Human-in-the-loop request'}
            <span className="block text-xs mt-1 opacity-60">
              Answer UI arrives in Phase C
            </span>
          </div>
        )
      }

      default:
        return <UnknownRow key={key} event={event} />
    }
  }

  const effectiveStatus: Status = isTerminal
    ? (session?.status ?? 'completed')
    : connStatus === 'connecting'
    ? 'connecting'
    : 'running'

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ fontFamily: 'var(--font-outfit), system-ui, sans-serif' }}
    >
      {/* Top bar */}
      <header
        className="flex items-center gap-4 px-5 h-14 border-b shrink-0"
        style={{ borderColor: 'rgba(240, 230, 219, 0.08)' }}
      >
        <Link
          href="/cockpit"
          className="text-sm transition-opacity hover:opacity-70 shrink-0"
          style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
        >
          ← runs
        </Link>

        <span className="w-px h-4 shrink-0" style={{ background: 'rgba(240, 230, 219, 0.08)' }} />

        <span
          className="text-sm font-mono text-xs"
          style={{ color: '#7A6A5F', fontFamily: 'var(--font-fira-code), monospace' }}
        >
          {session?.display_id ?? runId.slice(0, 16)}
        </span>

        <span className="flex-1 text-sm truncate" style={{ color: '#EDE3D9' }}>
          {session?.topic ?? '…'}
        </span>

        <div className="flex items-center gap-3 shrink-0">
          <StatusBadge status={effectiveStatus} />
          {!isTerminal && (
            <span
              className="text-xs font-mono tabular-nums"
              style={{ color: '#7A6A5F', fontFamily: 'var(--font-fira-code), monospace' }}
            >
              {fmtDuration(elapsed)}
            </span>
          )}
          {isTerminal && session?.duration && (
            <span
              className="text-xs font-mono"
              style={{ color: '#7A6A5F', fontFamily: 'var(--font-fira-code), monospace' }}
            >
              {fmtDuration(session.duration)}
            </span>
          )}
        </div>
      </header>

      {/* Main content: feed + inspector */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Activity feed */}
        <div className="flex-1 flex flex-col min-w-0 border-r" style={{ borderColor: 'rgba(240, 230, 219, 0.08)' }}>
          <div
            className="px-3 py-2 border-b text-xs tracking-widest uppercase font-semibold"
            style={{
              borderColor: 'rgba(240, 230, 219, 0.06)',
              color: '#7A6A5F',
              fontFamily: 'var(--font-syne), system-ui, sans-serif',
            }}
          >
            Activity
          </div>

          <div
            ref={feedRef}
            className="flex-1 overflow-y-auto px-5 py-4 space-y-1 custom-scrollbar"
            style={{ background: '#0C0A09' }}
          >
            {events.length === 0 && connStatus === 'connecting' && (
              <div className="text-sm pt-8 text-center" style={{ color: '#7A6A5F' }}>
                Connecting to run…
              </div>
            )}
            {events.length === 0 && connStatus === 'live' && (
              <div className="text-sm pt-8 text-center" style={{ color: '#7A6A5F' }}>
                Waiting for first event…
              </div>
            )}
            {events.map((ev, i) => renderFeedItem(ev, i))}
          </div>
        </div>

        {/* Inspector panel */}
        <div
          className="w-80 shrink-0 overflow-y-auto flex flex-col gap-4 p-4 custom-scrollbar"
          style={{ background: '#0E0C0A' }}
        >
          <CostMeter usage={usageData} liveUsage={liveUsage} />
          <TreeInspector tree={tree} />

          {/* Meta */}
          {session && (
            <div
              className="rounded-xl border p-4 space-y-2"
              style={{ background: '#161412', borderColor: 'rgba(240, 230, 219, 0.08)' }}
            >
              <h3
                className="text-xs tracking-widest uppercase font-semibold"
                style={{ color: '#7A6A5F', fontFamily: 'var(--font-syne), system-ui, sans-serif' }}
              >
                Run Info
              </h3>
              {[
                ['engine', session.agent_type],
                ['mode', session.research_mode],
                ['started', new Date(session.started_at).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between text-xs gap-2">
                  <span style={{ color: '#7A6A5F' }}>{k}</span>
                  <span
                    className="font-mono truncate"
                    style={{ color: '#EDE3D9', fontFamily: 'var(--font-fira-code), monospace' }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Deferred features note */}
          <div
            className="rounded-lg border p-3 text-xs space-y-1"
            style={{ borderColor: 'rgba(240, 230, 219, 0.05)', color: '#7A6A5F' }}
          >
            <div className="font-semibold">Deferred in v0</div>
            <div>HITL answer UI (Phase C)</div>
            <div>Auth / SSE tickets (Phase D)</div>
            <div>Live workspace / files (Phase E)</div>
            <div>Connections panel (Phase G)</div>
          </div>
        </div>
      </div>
    </div>
  )
}
