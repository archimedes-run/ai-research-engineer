'use client'

import { use, useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { apiUrl } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types — mirrors core/events.py
// ---------------------------------------------------------------------------

interface BaseEvent {
  type: string
  timestamp?: string
  seq?: number
}
interface MessageEvent extends BaseEvent { type: 'message'; content: string; is_thought?: boolean; is_partial?: boolean }
interface FunctionCallEvent extends BaseEvent { type: 'function_call'; name: string; arguments?: Record<string, unknown> }
interface FunctionResponseEvent extends BaseEvent { type: 'function_response'; name: string; response?: unknown }
interface UsageEvent extends BaseEvent { type: 'usage'; model?: string; usage?: { input_tokens?: number; cached_input_tokens?: number; output_tokens?: number } }
interface CompletedEvent extends BaseEvent { type: 'completed'; duration?: number; files_created?: string[] }
interface ErrorEvent extends BaseEvent { type: 'error'; content: string }
interface StageEvent extends BaseEvent { type: 'stage'; stage?: string; label?: string }
interface HitlEvent extends BaseEvent { type: 'hitl_request'; request_id?: string; gate_key?: string; question?: string; context_md?: string; options?: string[] }

type FeedEvent = { type: string; seq?: number; timestamp?: string; [key: string]: unknown }

interface FileNode { path: string; type: 'file' | 'dir'; size: number; children?: FileNode[] }
interface FileContent { path: string; content?: string; binary?: boolean; too_large?: boolean; size?: number; redacted?: boolean }
interface UsageTotals { input_tokens: number; cached_input_tokens: number; output_tokens: number; cost_usd: number }
interface UsageResponse { totals: UsageTotals; by_model: { model: string; cost_usd: number }[] }
interface Session { session_id: string; display_id: string; topic: string; status: string; agent_type: string; research_mode: string; started_at: string; hitl_enabled?: boolean | number }
interface TreeData { stats: { total_nodes: number; by_type: Record<string, number> }; gaps: { reason?: string }[] }

function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

// ---------------------------------------------------------------------------
// Design tokens — warm light brand theme
// ---------------------------------------------------------------------------
const C = {
  bg: '#F5EFE8',
  surface: '#FDFAF7',
  surface2: '#EDE5DC',
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
// Research stages
// ---------------------------------------------------------------------------
const STAGES = [
  { key: 'ideation', label: 'Ideation' },
  { key: 'literature', label: 'Literature' },
  { key: 'experiment', label: 'Experiment' },
  { key: 'writing', label: 'Writing' },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}
function fmtCost(usd: number): string {
  if (usd < 0.001) return '<$0.001'
  return usd < 1 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`
}
function fmtTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`
  return `${(n / 1_000_000).toFixed(2)}M`
}
function fileExt(path: string): string {
  const name = path.split('/').pop() ?? path
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : ''
}
function fileName(path: string): string { return path.split('/').pop() ?? path }

const WRITE_TOOLS = new Set(['write_file', 'edit_file', 'create_file', 'write', 'edit', 'patch_file'])
function extractEditPath(ev: FeedEvent): string | null {
  if (ev.type !== 'function_call') return null
  const name = ((ev as unknown as FunctionCallEvent).name ?? '').toLowerCase()
  if (!WRITE_TOOLS.has(name) && !name.includes('write') && !name.includes('edit')) return null
  const args = (ev as unknown as FunctionCallEvent).arguments ?? {}
  return (args.path ?? args.file_path ?? null) as string | null
}
function inferStageFromEvent(ev: FeedEvent): string | null {
  const t = ev.type
  if (t === 'stage') {
    const s = ((ev as unknown as StageEvent).stage ?? (ev as unknown as StageEvent).label ?? '').toLowerCase()
    if (s.includes('idea') || s.includes('plan')) return 'ideation'
    if (s.includes('liter') || s.includes('search') || s.includes('paper')) return 'literature'
    if (s.includes('exp') || s.includes('impl') || s.includes('code')) return 'experiment'
    if (s.includes('writ') || s.includes('paper') || s.includes('manu')) return 'writing'
  }
  if (t === 'function_call') {
    const name = ((ev as unknown as FunctionCallEvent).name ?? '').toLowerCase()
    if (name.includes('search') || name.includes('fetch')) return 'literature'
    if (name.includes('write') || name.includes('edit') || name.includes('exec') || name.includes('run')) return 'experiment'
    const args = (ev as unknown as FunctionCallEvent).arguments ?? {}
    const path = String(args.path ?? args.file_path ?? '')
    if (path.includes('manuscript') || path.includes('paper') || path.includes('.tex')) return 'writing'
    if (path.includes('literature') || path.includes('knowledge')) return 'literature'
    if (path.includes('result') || path.includes('experiment') || path.includes('.py')) return 'experiment'
  }
  return null
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; pulse: boolean }> = {
    running: { label: 'running', color: C.amber, pulse: true },
    awaiting_input: { label: 'waiting for you', color: C.amber, pulse: true },
    completed: { label: 'done', color: C.green, pulse: false },
    error: { label: 'error', color: C.brand, pulse: false },
    failed: { label: 'failed', color: C.brand, pulse: false },
    interrupted: { label: 'stopped', color: C.muted, pulse: false },
  }
  const s = map[status] ?? { label: status, color: C.muted, pulse: false }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded-full border"
      style={{ borderColor: `${s.color}40`, color: s.color, background: `${s.color}10` }}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.pulse ? 'animate-pulse' : ''}`} style={{ background: s.color }} />
      {s.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Stage progress tracker (left sidebar)
// ---------------------------------------------------------------------------
function StageProgress({ completedStages, activeStage, isTerminal }: {
  completedStages: Set<string>; activeStage: string | null; isTerminal: boolean
}) {
  return (
    <div className="space-y-1">
      {STAGES.map((stage, i) => {
        const done = completedStages.has(stage.key)
        const active = !done && activeStage === stage.key && !isTerminal
        const pending = !done && !active
        return (
          <div key={stage.key} className="flex items-center gap-3">
            {/* connector line */}
            <div className="flex flex-col items-center" style={{ width: 20 }}>
              {i > 0 && (
                <div className="w-px flex-1 mb-1" style={{ height: 8, background: done ? C.green : C.border2 }} />
              )}
              <div
                className="w-4 h-4 rounded-full flex items-center justify-center text-xs flex-shrink-0"
                style={{
                  background: done ? C.green : active ? C.amber : C.border,
                  color: done || active ? '#fff' : C.muted,
                  border: `2px solid ${done ? C.green : active ? C.amber : C.border2}`,
                }}
              >
                {done ? '✓' : active ? '' : ''}
              </div>
            </div>
            <span
              className="text-xs"
              style={{
                color: done ? C.text : active ? C.amber : C.muted,
                fontWeight: done || active ? 600 : 400,
                fontFamily: 'var(--font-outfit)',
              }}
            >
              {stage.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Compact activity row (sidebar)
// ---------------------------------------------------------------------------
function CompactRow({ ev }: { ev: FeedEvent }) {
  if (ev.type === 'message') {
    const msg = ev as unknown as MessageEvent
    if (msg.is_thought) return null
    return (
      <div className="flex gap-2 py-1.5 border-b" style={{ borderColor: C.border }}>
        <div className="w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center text-xs mt-0.5"
          style={{ background: `${C.brand}15`, color: C.brand, fontSize: 8 }}>A</div>
        <p className="text-xs leading-relaxed line-clamp-2" style={{ color: C.text, fontFamily: 'var(--font-outfit)' }}>
          {msg.content}
        </p>
      </div>
    )
  }
  if (ev.type === 'function_call') {
    const fc = ev as unknown as FunctionCallEvent
    const args = fc.arguments ?? {}
    const pathStr = typeof args.path === 'string' ? args.path : typeof args.file_path === 'string' ? args.file_path : null
    return (
      <div className="flex items-center gap-1.5 py-1 border-b" style={{ borderColor: C.border }}>
        <span style={{ fontSize: 9, color: C.blue }}>▶</span>
        <span className="text-xs font-mono truncate" style={{ color: C.blue }}>{fc.name}</span>
        {pathStr && <span className="text-xs truncate opacity-60" style={{ color: C.muted }}>{fileName(pathStr)}</span>}
      </div>
    )
  }
  if (ev.type === 'stage') {
    const label = (ev as unknown as StageEvent).stage ?? (ev as unknown as StageEvent).label ?? 'stage'
    return (
      <div className="text-xs py-1 font-semibold uppercase tracking-wider" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>
        — {label}
      </div>
    )
  }
  if (ev.type === 'completed') return (
    <div className="text-xs py-1 font-semibold" style={{ color: C.green }}>✓ Run completed</div>
  )
  if (ev.type === 'error') return (
    <div className="text-xs py-1 font-semibold" style={{ color: C.brand }}>✗ Run failed</div>
  )
  return null
}

// ---------------------------------------------------------------------------
// Full feed renderers (Activity tab)
// ---------------------------------------------------------------------------
function MessageRow({ ev, index, events }: { ev: MessageEvent; index: number; events: FeedEvent[] }) {
  void index; void events
  const [open, setOpen] = useState(false)
  if (ev.is_thought) return (
    <div className="my-1">
      <button onClick={() => setOpen(v => !v)} className="flex items-center gap-1.5 text-xs px-2 py-1 rounded hover:bg-black/5 transition-colors" style={{ color: C.muted }}>
        <span style={{ fontSize: 7 }}>{open ? '▼' : '▶'}</span> reasoning
      </button>
      {open && <div className="mt-1 mx-2 px-3 py-2 rounded border-l-2 text-xs leading-relaxed" style={{ borderColor: `${C.muted}50`, color: C.muted, background: C.surface2 }}>{ev.content}</div>}
    </div>
  )
  return (
    <div className="flex gap-3 my-3">
      <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5" style={{ background: `${C.brand}15`, color: C.brand }}>A</div>
      <div className="flex-1 text-sm leading-relaxed rounded-xl px-4 py-3 shadow-sm" style={{ background: C.surface, color: C.text, border: `1px solid ${C.border}`, fontFamily: 'var(--font-outfit)' }}>
        {ev.content}
        {ev.is_partial && <span className="inline-block w-1.5 h-3 ml-1 align-middle bg-current animate-pulse rounded-sm" />}
      </div>
    </div>
  )
}

function ToolRow({ ev, index, events }: { ev: FunctionCallEvent; index: number; events: FeedEvent[] }) {
  const [open, setOpen] = useState(false)
  const response = events.slice(index + 1).find(e => e.type === 'function_response' && (e as unknown as FunctionResponseEvent).name === ev.name) as unknown as FunctionResponseEvent | undefined
  const args = ev.arguments ?? {}
  const argStr = JSON.stringify(args, null, 2)
  const respStr = response?.response != null ? (typeof response.response === 'string' ? response.response : JSON.stringify(response.response, null, 2)) : null

  return (
    <div className="my-1.5">
      <button onClick={() => setOpen(v => !v)} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border w-full text-left transition-all"
        style={{ borderColor: open ? `${C.blue}40` : C.border, background: open ? `${C.blue}05` : C.surface, color: C.muted }}>
        <span style={{ fontSize: 7, color: C.blue }}>{open ? '▼' : '▶'}</span>
        <span style={{ color: C.blue, fontFamily: 'var(--font-fira-code)', fontSize: 11 }}>{ev.name}</span>
        {typeof args.path === 'string' && <span className="ml-1 truncate max-w-xs" style={{ color: `${C.muted}`, fontSize: 10 }}>{args.path}</span>}
        {response && <span className="ml-auto" style={{ color: C.green, fontSize: 9 }}>✓</span>}
      </button>
      {open && (
        <div className="mt-1 mx-2 rounded-lg border text-xs overflow-hidden" style={{ borderColor: `${C.blue}20`, background: '#F8FAFC' }}>
          {argStr !== '{}' && <div className="px-3 py-2 border-b" style={{ borderColor: `${C.border}` }}>
            <div className="text-xs mb-1 uppercase tracking-wider" style={{ color: C.muted }}>args</div>
            <pre className="overflow-x-auto" style={{ color: C.text, fontFamily: 'var(--font-fira-code)', fontSize: 11, lineHeight: 1.5 }}>{argStr}</pre>
          </div>}
          {respStr && <div className="px-3 py-2">
            <div className="text-xs mb-1 uppercase tracking-wider" style={{ color: C.muted }}>response</div>
            <pre className="overflow-x-auto max-h-40" style={{ color: C.muted, fontFamily: 'var(--font-fira-code)', fontSize: 11, lineHeight: 1.5 }}>{respStr.slice(0, 2000)}{respStr.length > 2000 ? '\n…' : ''}</pre>
          </div>}
        </div>
      )}
    </div>
  )
}

function HitlCard({ ev, runId, onAnswered }: { ev: HitlEvent; runId?: string; onAnswered?: () => void }) {
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [fetchedQ, setFetchedQ] = useState<string | null>(null)
  const [fetchedCtx, setFetchedCtx] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    fetch(apiUrl(`/api/sessions/${runId}/hitl`), { headers: apiHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then((d: { pending?: { question?: string; context_md?: string } } | null) => {
        if (d?.pending) {
          if (d.pending.question) setFetchedQ(d.pending.question)
          if (d.pending.context_md) setFetchedCtx(d.pending.context_md)
        }
      })
      .catch(() => null)
  }, [runId])

  const question = fetchedQ ?? ev.question ?? ''
  const contextMd = fetchedCtx ?? ev.context_md ?? ''

  async function submit(ans: string) {
    if (!runId || submitting || submitted) return
    setSubmitting(true)
    try {
      const r = await fetch(apiUrl(`/api/sessions/${runId}/answer`), {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ answer: ans }),
      })
      if (r.ok) { setSubmitted(true); onAnswered?.() }
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) return (
    <div className="rounded-xl border px-4 py-3 my-4" style={{ borderColor: `${C.green}40`, background: `${C.green}08` }}>
      <span className="text-xs font-semibold" style={{ color: C.green }}>✓ Response submitted — resuming…</span>
    </div>
  )

  return (
    <div className="rounded-xl border px-4 py-4 my-4" style={{ borderColor: `${C.amber}40`, background: `${C.amber}08` }}>
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.amber }} />
        <span className="text-xs tracking-widest uppercase font-semibold" style={{ color: C.amber }}>Awaiting your review</span>
      </div>
      {question && <p className="text-sm mb-3" style={{ color: C.text }}>{question}</p>}
      {contextMd && (
        <pre className="text-xs rounded-lg p-3 mb-3 border overflow-auto" style={{ borderColor: C.border, background: C.surface, color: C.muted, fontFamily: 'var(--font-fira-code)', whiteSpace: 'pre-wrap', maxHeight: 160 }}>
          {contextMd}
        </pre>
      )}
      {runId && (
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={() => submit('approve')}
            disabled={submitting}
            className="text-xs px-3 py-1.5 rounded-lg border font-medium transition-all flex-shrink-0"
            style={{ borderColor: `${C.green}50`, background: submitting ? 'transparent' : `${C.green}10`, color: submitting ? C.muted : C.green, cursor: submitting ? 'not-allowed' : 'pointer' }}
          >
            {submitting ? 'Submitting…' : 'Approve & continue'}
          </button>
          <textarea
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            placeholder="Or type feedback…"
            rows={1}
            disabled={submitting}
            className="flex-1 text-xs px-3 py-1.5 rounded-lg border outline-none resize-none"
            style={{ borderColor: C.border, background: C.surface, color: C.text, fontFamily: 'var(--font-outfit)', minHeight: 34 }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (answer.trim()) submit(answer.trim()) } }}
          />
          <button
            onClick={() => { if (answer.trim()) submit(answer.trim()) }}
            disabled={!answer.trim() || submitting}
            className="text-xs px-3 py-1.5 rounded-lg border font-medium transition-all flex-shrink-0"
            style={{
              borderColor: answer.trim() && !submitting ? `${C.brand}50` : C.border,
              background: answer.trim() && !submitting ? `${C.brand}10` : 'transparent',
              color: answer.trim() && !submitting ? C.brand : C.muted,
              cursor: answer.trim() && !submitting ? 'pointer' : 'not-allowed',
            }}
          >
            Submit
          </button>
        </div>
      )}
    </div>
  )
}

function TerminalBanner({ type, ev }: { type: 'completed' | 'error'; ev: FeedEvent }) {
  const isOk = type === 'completed'
  const color = isOk ? C.green : C.brand
  const label = isOk ? 'Run completed' : 'Run failed'
  const detail = isOk
    ? `${((ev as unknown as CompletedEvent).duration ?? 0).toFixed(1)}s · ${(ev as unknown as CompletedEvent).files_created?.length ?? 0} files`
    : (ev as unknown as ErrorEvent).content
  return (
    <div className="rounded-xl border px-4 py-3 my-4" style={{ borderColor: `${color}40`, background: `${color}08` }}>
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold" style={{ color, fontFamily: 'var(--font-syne)' }}>{label}</span>
        {detail && <span className="text-xs" style={{ color: C.muted }}>{detail}</span>}
      </div>
    </div>
  )
}

function FeedRow({ ev, index, events }: { ev: FeedEvent; index: number; events: FeedEvent[] }) {
  if (ev.type === 'message') return <MessageRow ev={ev as unknown as MessageEvent} index={index} events={events} />
  if (ev.type === 'function_call') return <ToolRow ev={ev as unknown as FunctionCallEvent} index={index} events={events} />
  if (ev.type === 'function_response') {
    const hasPair = events.slice(0, index).some(e => e.type === 'function_call' && (e as unknown as FunctionCallEvent).name === (ev as unknown as FunctionResponseEvent).name)
    if (hasPair) return null
    return <ToolRow ev={{ type: 'function_call', name: (ev as unknown as FunctionResponseEvent).name, arguments: {} } as unknown as FunctionCallEvent} index={index} events={events} />
  }
  if (ev.type === 'stage') {
    const label = (ev as unknown as StageEvent).stage ?? (ev as unknown as StageEvent).label ?? 'stage'
    return <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px" style={{ background: C.border2 }} />
      <span className="text-xs tracking-widest uppercase px-2" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>{label}</span>
      <div className="flex-1 h-px" style={{ background: C.border2 }} />
    </div>
  }
  if (ev.type === 'completed') return <TerminalBanner type="completed" ev={ev} />
  if (ev.type === 'error') return <TerminalBanner type="error" ev={ev} />
  if (ev.type === 'keepalive' || ev.type === 'usage') return null
  return <div className="my-1 px-3 py-1 text-xs rounded border" style={{ borderColor: C.border, color: C.muted }}><span className="font-mono">{ev.type}</span></div>
}

// ---------------------------------------------------------------------------
// Paper viewer (reads manuscript/*.md or knowledge_base/*.md)
// ---------------------------------------------------------------------------
const PAPER_EXTS = new Set(['md', 'tex', 'txt'])

function PaperViewer({ runId, isTerminal }: { runId: string; isTerminal: boolean }) {
  const [paperContent, setPaperContent] = useState<string | null>(null)
  const [paperPath, setPaperPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchPaper = useCallback(async () => {
    const res = await fetch(apiUrl(`/api/sessions/${runId}/files`), { headers: apiHeaders() }).catch(() => null)
    if (!res?.ok) return
    const tree = await res.json().catch(() => [])

    // Find the best paper candidate
    type NodeLike = { path: string; type: string; children?: NodeLike[] }
    function findCandidates(nodes: NodeLike[], prefix = ''): string[] {
      const results: string[] = []
      for (const n of nodes) {
        if (n.type === 'file') {
          const ext = fileExt(n.path)
          if (PAPER_EXTS.has(ext)) results.push(n.path)
        } else if (n.children) {
          results.push(...findCandidates(n.children, n.path))
        }
      }
      void prefix
      return results
    }
    const candidates = findCandidates(tree)
    // Prioritize manuscript > knowledge_base > results
    const sorted = candidates.sort((a, b) => {
      const score = (p: string) => {
        if (p.includes('manuscript')) return 0
        if (p.includes('knowledge_base') || p.includes('literature')) return 1
        if (p.includes('results')) return 2
        return 3
      }
      return score(a) - score(b)
    })

    if (sorted.length === 0) { setLoading(false); return }
    const path = sorted[0]

    const fc = await fetch(apiUrl(`/api/sessions/${runId}/files/${path}`), { headers: apiHeaders() }).catch(() => null)
    if (!fc?.ok) { setLoading(false); return }
    const data = await fc.json().catch(() => null)
    if (data?.content) { setPaperContent(data.content); setPaperPath(path) }
    setLoading(false)
  }, [runId])

  useEffect(() => {
    fetchPaper()
    if (isTerminal) return
    const id = setInterval(fetchPaper, 5000)
    return () => clearInterval(id)
  }, [isTerminal, fetchPaper])

  if (loading) return (
    <div className="flex items-center justify-center h-full text-sm" style={{ color: C.muted }}>Loading research output…</div>
  )
  if (!paperContent) return (
    <div className="flex flex-col items-center justify-center h-full gap-3" style={{ color: C.muted }}>
      <p className="text-sm">No research output yet — the agent is still working.</p>
      {!isTerminal && <p className="text-xs">This panel refreshes automatically.</p>}
    </div>
  )

  // Simple markdown renderer
  const lines = paperContent.split('\n')
  return (
    <div className="h-full overflow-y-auto">
      {paperPath && (
        <div className="px-8 py-2 text-xs border-b sticky top-0" style={{ borderColor: C.border, color: C.muted, background: C.surface }}>
          {paperPath}
        </div>
      )}
      <article
        className="max-w-3xl mx-auto px-8 py-10"
        style={{ fontFamily: 'var(--font-cormorant), Georgia, serif', color: C.text }}
      >
        {lines.map((line, i) => {
          if (line.startsWith('# ')) return <h1 key={i} className="text-3xl font-bold mt-8 mb-4 text-center" style={{ fontFamily: 'var(--font-cormorant)' }}>{line.slice(2)}</h1>
          if (line.startsWith('## ')) return <h2 key={i} className="text-xl font-semibold mt-6 mb-3" style={{ fontFamily: 'var(--font-syne)' }}>{line.slice(3)}</h2>
          if (line.startsWith('### ')) return <h3 key={i} className="text-base font-semibold mt-4 mb-2" style={{ fontFamily: 'var(--font-syne)' }}>{line.slice(4)}</h3>
          if (line.startsWith('- ') || line.startsWith('* ')) return <li key={i} className="ml-4 text-sm leading-relaxed mb-1">{line.slice(2)}</li>
          if (line.trim() === '') return <div key={i} className="h-3" />
          return <p key={i} className="text-sm leading-relaxed mb-2">{line}</p>
        })}
      </article>
    </div>
  )
}

// ---------------------------------------------------------------------------
// File tree + code viewer (Files tab)
// ---------------------------------------------------------------------------
const EXT_TO_LANG: Record<string, string> = {
  py: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript', json: 'json',
  md: 'markdown', sh: 'bash', css: 'css', html: 'xml', yaml: 'yaml', yml: 'yaml',
  toml: 'ini', rs: 'rust', go: 'go', tex: 'latex',
}
const FILE_COLORS: Record<string, string> = {
  py: '#3B82F6', ts: '#3B82F6', tsx: '#61DAFB', js: '#F59E0B',
  json: '#10B981', md: '#8B5CF6', sh: '#22C55E', tex: C.brand,
  yaml: '#F59E0B', yml: '#F59E0B', toml: C.brand,
}

function FileIcon({ ext }: { ext: string }) {
  const c = FILE_COLORS[ext] ?? C.muted
  return <span className="w-3.5 h-3.5 rounded-sm flex-shrink-0 flex items-center justify-center" style={{ background: `${c}20`, color: c, fontSize: 7, fontWeight: 700 }}>{ext ? ext[0].toUpperCase() : '·'}</span>
}

function FileTreeNode({ node, expanded, onToggle, onSelect, selectedPath, editingPath, depth }: {
  node: FileNode; expanded: Set<string>; onToggle: (p: string) => void; onSelect: (p: string) => void; selectedPath: string | null; editingPath: string | null; depth: number
}) {
  const name = fileName(node.path)
  if (node.type === 'dir') {
    const isOpen = expanded.has(node.path)
    return (
      <div>
        <button onClick={() => onToggle(node.path)} className="flex items-center gap-1.5 w-full text-left px-2 py-0.5 rounded text-xs hover:bg-black/5 transition-colors" style={{ paddingLeft: `${depth * 12 + 8}px`, color: C.muted }}>
          <span style={{ fontSize: 7 }}>{isOpen ? '▼' : '▶'}</span>
          <span style={{ fontFamily: 'var(--font-fira-code)' }}>{name}/</span>
        </button>
        {isOpen && node.children?.map(c => <FileTreeNode key={c.path} node={c} expanded={expanded} onToggle={onToggle} onSelect={onSelect} selectedPath={selectedPath} editingPath={editingPath} depth={depth + 1} />)}
      </div>
    )
  }
  const ext = fileExt(name)
  const isSelected = selectedPath === node.path
  return (
    <button onClick={() => onSelect(node.path)} className="flex items-center gap-1.5 w-full text-left px-2 py-0.5 rounded text-xs transition-colors" style={{ paddingLeft: `${depth * 12 + 8}px`, background: isSelected ? `${C.brand}12` : 'transparent', color: isSelected ? C.brand : C.text }} title={node.path}>
      <FileIcon ext={ext} />
      <span className="truncate" style={{ fontFamily: 'var(--font-fira-code)' }}>{name}</span>
      {editingPath === node.path && <span className="ml-auto" style={{ color: C.amber, fontSize: 10 }}>✎</span>}
    </button>
  )
}

function CodeViewer({ file }: { file: FileContent | null }) {
  const [highlighted, setHighlighted] = useState<string | null>(null)
  useEffect(() => {
    if (!file?.content) { setHighlighted(null); return }
    const lang = EXT_TO_LANG[fileExt(file.path)]
    import('highlight.js').then(({ default: hljs }) => {
      try {
        const r = lang ? hljs.highlight(file.content!, { language: lang }) : hljs.highlightAuto(file.content!)
        setHighlighted(r.value)
      } catch { setHighlighted(null) }
    }).catch(() => setHighlighted(null))
  }, [file])

  if (!file) return <div className="flex items-center justify-center h-full text-sm" style={{ color: C.muted }}>Select a file to view</div>
  if (file.binary) return <div className="flex items-center justify-center h-full text-sm" style={{ color: C.muted }}>Binary file — no preview</div>
  if (file.too_large) return <div className="flex items-center justify-center h-full text-sm" style={{ color: C.muted }}>File too large to preview</div>

  return (
    <div className="h-full overflow-auto" style={{ background: '#F8FAFC' }}>
      <style>{`
        .hljs-light{background:transparent;color:#24292E}
        .hljs-keyword{color:#D73A49}.hljs-string{color:#032F62}
        .hljs-number{color:#005CC5}.hljs-comment{color:#6A737D;font-style:italic}
        .hljs-function .hljs-title,.hljs-title.function_{color:#6F42C1}
        .hljs-class .hljs-title,.hljs-title.class_{color:#E36209}
        .hljs-built_in{color:#E36209}.hljs-type{color:#005CC5}
        .hljs-attr{color:#005CC5}.hljs-meta{color:#6A737D}
        .hljs-tag{color:#22863A}.hljs-name{color:#22863A}
        .hljs-literal{color:#005CC5}.hljs-operator{color:#D73A49}
        .hljs-punctuation{color:#6A737D}.hljs-section{color:#6F42C1;font-weight:bold}
        .hljs-link{color:#032F62;text-decoration:underline}
        .hljs-selector-tag{color:#22863A}.hljs-property{color:#005CC5}
      `}</style>
      {file.redacted && <div className="px-4 py-1.5 text-xs flex items-center gap-2 border-b sticky top-0" style={{ background: `${C.amber}12`, borderColor: `${C.amber}30`, color: C.amber }}>⚠ Secrets redacted</div>}
      <pre className="p-4 text-xs leading-relaxed" style={{ fontFamily: 'var(--font-fira-code)', margin: 0, color: '#24292E' }}>
        {highlighted != null
          ? <code className="hljs-light" dangerouslySetInnerHTML={{ __html: highlighted }} />
          : <code>{file.content}</code>}
      </pre>
    </div>
  )
}

function FilesTab({ runId, isTerminal, editingPath }: { runId: string; isTerminal: boolean; editingPath: string | null }) {
  const [fileTree, setFileTree] = useState<FileNode[] | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [followAgent, setFollowAgent] = useState(true)

  const fetchTree = useCallback(async () => {
    const res = await fetch(apiUrl(`/api/sessions/${runId}/files`), { headers: apiHeaders() }).catch(() => null)
    if (!res?.ok) return
    const data: FileNode[] = await res.json().catch(() => [])
    setFileTree(data)
    setExpandedDirs(prev => {
      if (prev.size > 0) return prev
      const next = new Set(prev)
      for (const n of data) if (n.type === 'dir') next.add(n.path)
      return next
    })
  }, [runId])

  useEffect(() => {
    fetchTree()
    if (isTerminal) return
    const id = setInterval(fetchTree, 2000)
    return () => clearInterval(id)
  }, [isTerminal, fetchTree])

  useEffect(() => {
    if (!followAgent || !editingPath) return
    setSelectedPath(editingPath)
    fetch(apiUrl(`/api/sessions/${runId}/files/${editingPath}`), { headers: apiHeaders() })
      .then(r => r.ok ? r.json() : null).then((d: FileContent | null) => { if (d) setFileContent(d) }).catch(() => null)
  }, [followAgent, editingPath, runId])

  const handleSelect = useCallback((path: string) => {
    setFollowAgent(false); setSelectedPath(path)
    fetch(apiUrl(`/api/sessions/${runId}/files/${path}`), { headers: apiHeaders() })
      .then(r => r.ok ? r.json() : null).then((d: FileContent | null) => { if (d) setFileContent(d) }).catch(() => null)
  }, [runId])

  return (
    <div className="flex h-full overflow-hidden">
      {/* Tree */}
      <div className="w-64 border-r overflow-y-auto flex-shrink-0 py-2" style={{ borderColor: C.border }}>
        <div className="flex items-center gap-2 px-3 pb-2 border-b mb-1" style={{ borderColor: C.border }}>
          {editingPath && <span className="text-xs font-mono truncate" style={{ color: C.amber }}>✎ {fileName(editingPath)}</span>}
          <button onClick={() => setFollowAgent(v => !v)} className="ml-auto text-xs px-2 py-0.5 rounded border flex-shrink-0" style={{ borderColor: followAgent ? `${C.green}50` : C.border, color: followAgent ? C.green : C.muted, background: followAgent ? `${C.green}08` : 'transparent' }}>
            {followAgent ? '⬤ follow' : '○ follow'}
          </button>
        </div>
        {fileTree === null ? <div className="px-3 text-xs" style={{ color: C.muted }}>Loading…</div>
          : fileTree.length === 0 ? <div className="px-3 text-xs" style={{ color: C.muted }}>No files yet</div>
            : fileTree.map(n => <FileTreeNode key={n.path} node={n} expanded={expandedDirs} onToggle={p => setExpandedDirs(prev => { const next = new Set(prev); next.has(p) ? next.delete(p) : next.add(p); return next })} onSelect={handleSelect} selectedPath={selectedPath} editingPath={editingPath} depth={0} />)}
      </div>
      {/* Viewer */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {selectedPath && (
          <div className="px-4 py-1.5 text-xs font-mono border-b flex items-center" style={{ borderColor: C.border, color: C.muted, background: C.surface }}>
            <span style={{ color: C.text }}>{selectedPath}</span>
            {fileContent?.size != null && <span className="ml-auto">{(fileContent.size / 1024).toFixed(1)} KB</span>}
          </div>
        )}
        <div className="flex-1 overflow-hidden"><CodeViewer file={fileContent} /></div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Knowledge Graph placeholder
// ---------------------------------------------------------------------------
function KnowledgeGraphTab() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4" style={{ color: C.muted }}>
      <div className="text-center max-w-sm">
        <p className="text-sm font-semibold mb-1" style={{ color: C.text }}>Knowledge Graph</p>
        <p className="text-xs leading-relaxed">A visual graph of concepts, citations, and relationships will appear here after the run completes.</p>
      </div>
      <span className="text-xs px-3 py-1.5 rounded-full border" style={{ borderColor: C.border, color: C.muted }}>Coming in Phase E+</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inspector tab (tree stats + connections stub)
// ---------------------------------------------------------------------------
function InspectorTab({ treeData }: { treeData: TreeData | null }) {
  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      <div>
        <h3 className="text-xs uppercase tracking-widest mb-3" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Argument Tree</h3>
        {treeData ? (
          <div className="rounded-xl border p-4 space-y-1.5" style={{ borderColor: C.border, background: C.surface }}>
            <div className="flex justify-between text-xs"><span style={{ color: C.muted }}>total nodes</span><span className="font-mono" style={{ color: C.text }}>{treeData.stats.total_nodes}</span></div>
            {Object.entries(treeData.stats.by_type ?? {}).map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs"><span style={{ color: C.muted }}>{k}</span><span className="font-mono" style={{ color: C.text }}>{v}</span></div>
            ))}
          </div>
        ) : <div className="text-xs" style={{ color: C.muted }}>Loading…</div>}
      </div>
      <div className="rounded-xl border p-4 opacity-50" style={{ borderColor: C.border }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs uppercase tracking-widest" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Connections</span>
          <span className="text-xs px-1.5 py-0.5 rounded border ml-auto" style={{ color: C.muted, borderColor: C.border, fontSize: 9 }}>Phase G</span>
        </div>
        <p className="text-xs" style={{ color: C.muted }}>External tool wiring — coming soon.</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
type Tab = 'activity' | 'paper' | 'files' | 'graph' | 'inspector'

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params)

  const [session, setSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [isTerminal, setIsTerminal] = useState(false)
  const [stopping, setStopping] = useState(false)
  const feedEndRef = useRef<HTMLDivElement>(null)
  const seenSeqs = useRef(new Set<number>())
  const lastSeqRef = useRef(0)
  const [sseVersion, setSseVersion] = useState(0)

  const [activeTab, setActiveTab] = useState<Tab>('activity')
  const [editingPath, setEditingPath] = useState<string | null>(null)
  const [chatMsg, setChatMsg] = useState('')

  // Stage tracking
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [activeStage, setActiveStage] = useState<string | null>('ideation')

  // Usage
  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [liveUsage, setLiveUsage] = useState<UsageTotals>({ input_tokens: 0, cached_input_tokens: 0, output_tokens: 0, cost_usd: 0 })

  // Argument tree
  const [treeData, setTreeData] = useState<TreeData | null>(null)

  // Elapsed
  const [startedAt, setStartedAt] = useState<Date | null>(null)
  const [elapsed, setElapsed] = useState(0)

  // ---------------------------------------------------------------------------
  // Fetch session
  // ---------------------------------------------------------------------------
  useEffect(() => {
    fetch(apiUrl(`/api/sessions/${runId}`), { headers: apiHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then((d: Session | null) => {
        if (!d) return
        setSession(d)
        setStartedAt(new Date(d.started_at))
        if (d.status !== 'running' && d.status !== 'awaiting_input') setIsTerminal(true)
      }).catch(() => null)
  }, [runId])

  // Elapsed timer
  useEffect(() => {
    if (isTerminal || !startedAt) return
    const id = setInterval(() => setElapsed(Date.now() - startedAt.getTime()), 1000)
    return () => clearInterval(id)
  }, [isTerminal, startedAt])

  // ---------------------------------------------------------------------------
  // Process event
  // ---------------------------------------------------------------------------
  const processEvent = useCallback((ev: FeedEvent) => {
    const seq = ev.seq as number | undefined
    if (seq != null) { if (seenSeqs.current.has(seq)) return; seenSeqs.current.add(seq) }
    if (ev.type === 'keepalive') return
    if (ev.type === 'usage') {
      const u = (ev as unknown as UsageEvent).usage ?? {}
      setLiveUsage(prev => ({ input_tokens: prev.input_tokens + (u.input_tokens ?? 0), cached_input_tokens: prev.cached_input_tokens + (u.cached_input_tokens ?? 0), output_tokens: prev.output_tokens + (u.output_tokens ?? 0), cost_usd: prev.cost_usd }))
      return
    }
    if (ev.type === 'completed' || ev.type === 'error') {
      setIsTerminal(true)
      fetch(apiUrl(`/api/sessions/${runId}/usage`), { headers: apiHeaders() }).then(r => r.ok ? r.json() : null).then((d: UsageResponse | null) => { if (d) setUsage(d) }).catch(() => null)
    }

    // Track stages
    const inferred = inferStageFromEvent(ev)
    if (inferred) {
      setActiveStage(prev => {
        const stageIdx = STAGES.findIndex(s => s.key === inferred)
        const prevIdx = STAGES.findIndex(s => s.key === prev)
        if (stageIdx > prevIdx) {
          // Mark previous stages as completed
          setCompletedStages(c => {
            const next = new Set(c)
            for (let i = 0; i < stageIdx; i++) next.add(STAGES[i].key)
            return next
          })
          return inferred
        }
        return prev
      })
    }

    // Track editing path
    const ep = extractEditPath(ev)
    if (ep) setEditingPath(ep)

    setEvents(prev => [...prev, ev])
  }, [runId])

  // ---------------------------------------------------------------------------
  // Stop
  // ---------------------------------------------------------------------------
  const handleStop = useCallback(async () => {
    if (stopping || isTerminal) return
    setStopping(true)
    try {
      await fetch(apiUrl(`/api/sessions/${runId}/stop`), {
        method: 'POST',
        headers: apiHeaders(),
      })
      // SSE will receive an error event + sentinel which sets isTerminal via processEvent
    } catch { /* ignore — SSE state update is the source of truth */ }
    finally {
      setStopping(false)
    }
  }, [runId, stopping, isTerminal])

  // ---------------------------------------------------------------------------
  // SSE
  // ---------------------------------------------------------------------------
  const handleAnswered = useCallback(() => {
    setSseVersion(v => v + 1)
  }, [])

  useEffect(() => {
    let es: EventSource | null = null
    let cancelled = false
    async function start() {
      const afterSeq = lastSeqRef.current
      const res = await fetch(apiUrl(`/api/sessions/${runId}/events?after_seq=${afterSeq}`), { headers: apiHeaders() }).catch(() => null)
      if (cancelled || !res?.ok) return
      const backfill: FeedEvent[] = await res.json().catch(() => [])
      if (cancelled) return
      for (const ev of backfill) {
        processEvent(ev)
        if ((ev.seq ?? 0) > lastSeqRef.current) lastSeqRef.current = ev.seq ?? 0
      }
      es = new EventSource(apiUrl(`/api/sessions/${runId}/stream?after_seq=${lastSeqRef.current}`))
      es.onmessage = e => {
        try {
          const ev: FeedEvent = JSON.parse(e.data)
          if ((ev.seq ?? 0) > lastSeqRef.current) lastSeqRef.current = ev.seq ?? 0
          processEvent(ev)
          if (ev.type === 'hitl_request') es?.close()
        } catch { /* ignore */ }
      }
      es.onerror = () => es?.close()
    }
    start()
    return () => { cancelled = true; es?.close() }
  }, [runId, processEvent, sseVersion])

  // Auto-scroll sidebar feed
  useEffect(() => { feedEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [events])

  // Usage + arg tree polls
  useEffect(() => {
    const fetch_ = async () => { const r = await fetch(apiUrl(`/api/sessions/${runId}/usage`), { headers: apiHeaders() }).catch(() => null); if (r?.ok) { const d = await r.json().catch(() => null); if (d) setUsage(d) } }
    fetch_()
    if (isTerminal) return
    const id = setInterval(fetch_, 10000)
    return () => clearInterval(id)
  }, [isTerminal, runId])

  useEffect(() => {
    const fetch_ = async () => { const r = await fetch(apiUrl(`/api/sessions/${runId}/tree`), { headers: apiHeaders() }).catch(() => null); if (r?.ok) { const d = await r.json().catch(() => null); if (d) setTreeData(d) } }
    fetch_()
    if (isTerminal) return
    const id = setInterval(fetch_, 6000)
    return () => clearInterval(id)
  }, [isTerminal, runId])

  const displayUsage = usage ?? (liveUsage.input_tokens > 0 ? { totals: liveUsage, by_model: [] } : null)
  const statusLabel = session?.status ?? (isTerminal ? 'completed' : 'running')

  const TABS: { id: Tab; label: string }[] = [
    { id: 'activity', label: 'Activity' },
    { id: 'paper', label: 'Paper' },
    { id: 'files', label: 'Files' },
    { id: 'graph', label: 'Knowledge Graph' },
    { id: 'inspector', label: 'Inspector' },
  ]

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: C.bg, color: C.text, fontFamily: 'var(--font-outfit)' }}>

      {/* ── Left sidebar ────────────────────────────────────────────────── */}
      <aside className="flex flex-col border-r flex-shrink-0 overflow-hidden" style={{ width: 260, background: C.sidebar, borderColor: C.border }}>

        {/* Logo + back */}
        <div className="px-5 py-4 border-b flex items-center gap-3" style={{ borderColor: C.border }}>
          <Link href="/cockpit" className="text-xs font-mono tracking-widest uppercase hover:opacity-70 transition-opacity" style={{ color: C.muted }}>← cockpit</Link>
          {!isTerminal && (
            <button
              onClick={handleStop}
              disabled={stopping}
              className="ml-auto text-xs px-2.5 py-1 rounded-lg border transition-all flex-shrink-0"
              style={{
                borderColor: stopping ? C.border : `${C.brand}50`,
                background: stopping ? 'transparent' : `${C.brand}08`,
                color: stopping ? C.muted : C.brand,
                cursor: stopping ? 'not-allowed' : 'pointer',
                fontFamily: 'var(--font-outfit)',
              }}
              title="Stop this run"
            >
              {stopping ? 'Stopping…' : '■ Stop'}
            </button>
          )}
        </div>

        {/* Session info */}
        <div className="px-5 py-4 border-b" style={{ borderColor: C.border }}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono" style={{ color: C.muted }}>{session?.display_id ?? runId.slice(0, 16)}</span>
            <StatusBadge status={statusLabel} />
            {session && (session.hitl_enabled ? (
              <span className="text-xs px-1.5 py-0.5 rounded border flex-shrink-0" style={{ borderColor: `${C.blue}40`, color: C.blue, background: `${C.blue}08` }}>Supervised</span>
            ) : (
              <span className="text-xs px-1.5 py-0.5 rounded border flex-shrink-0" style={{ borderColor: C.border, color: C.muted }}>Auto</span>
            ))}
          </div>
          {session?.topic && <p className="text-sm leading-snug mt-1" style={{ color: C.text }}>{session.topic}</p>}
          <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: C.muted }}>
            {!isTerminal && startedAt && <span>{fmtElapsed(elapsed)}</span>}
            {displayUsage && <span>{fmtCost(displayUsage.totals.cost_usd)}</span>}
            {displayUsage && <span>{fmtTokens(displayUsage.totals.input_tokens + displayUsage.totals.output_tokens)} tok</span>}
          </div>
        </div>

        {/* Stage progress */}
        <div className="px-5 py-4 border-b" style={{ borderColor: C.border }}>
          <div className="text-xs uppercase tracking-widest mb-3" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Progress</div>
          <StageProgress completedStages={completedStages} activeStage={activeStage} isTerminal={isTerminal} />
        </div>

        {/* Compact activity feed */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <div className="text-xs uppercase tracking-widest mb-2" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Activity</div>
          {events.length === 0 && !isTerminal && (
            <div className="flex items-center gap-2 text-xs" style={{ color: C.muted }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: C.amber }} />Connecting…
            </div>
          )}
          {events.map((ev, i) => <CompactRow key={ev.seq ?? `ev-${i}`} ev={ev} />)}
          <div ref={feedEndRef} />
        </div>
      </aside>

      {/* ── Right main area ──────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 overflow-hidden">

        {/* Tab bar */}
        <div className="flex items-center border-b px-4 gap-1 flex-shrink-0" style={{ borderColor: C.border, height: 44, background: C.surface }}>
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className="px-4 py-1.5 text-sm rounded-lg transition-colors"
              style={{ fontFamily: 'var(--font-outfit)', color: activeTab === tab.id ? C.brand : C.muted, background: activeTab === tab.id ? `${C.brand}10` : 'transparent', fontWeight: activeTab === tab.id ? 600 : 400 }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden" style={{ background: activeTab === 'activity' ? C.bg : C.surface }}>
          {activeTab === 'activity' && (
            <div className="h-full overflow-y-auto px-6 py-4 max-w-3xl mx-auto">
              {events.length === 0 && !isTerminal && (
                <div className="flex items-center gap-2 mt-6 text-sm" style={{ color: C.muted }}>
                  <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.amber }} />
                  Connecting to stream…
                </div>
              )}
              {events.map((ev, i) =>
                ev.type === 'hitl_request'
                  ? <HitlCard key={ev.seq ?? `ev-${i}`} ev={ev as unknown as HitlEvent} runId={runId} onAnswered={handleAnswered} />
                  : <FeedRow key={ev.seq ?? `ev-${i}`} ev={ev} index={i} events={events} />
              )}
            </div>
          )}
          {activeTab === 'paper' && <PaperViewer runId={runId} isTerminal={isTerminal} />}
          {activeTab === 'files' && <FilesTab runId={runId} isTerminal={isTerminal} editingPath={editingPath} />}
          {activeTab === 'graph' && <KnowledgeGraphTab />}
          {activeTab === 'inspector' && <InspectorTab treeData={treeData} />}
        </div>

        {/* ── Chat / HITL input bar ─────────────────────────────────────── */}
        <div className="flex-shrink-0 border-t px-4 py-3" style={{ borderColor: C.border, background: C.surface }}>
          <div className="max-w-3xl mx-auto flex items-end gap-3">
            <div className="flex-1 rounded-xl border overflow-hidden" style={{ borderColor: C.border, background: C.bg }}>
              <textarea
                rows={1}
                value={chatMsg}
                onChange={e => {
                  setChatMsg(e.target.value)
                  // auto-grow: reset then set to scrollHeight
                  e.target.style.height = 'auto'
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`
                }}
                placeholder="Send a message to the agent…"
                className="w-full px-4 py-2.5 text-sm leading-relaxed resize-none outline-none block"
                style={{
                  fontFamily: 'var(--font-outfit)',
                  color: C.text,
                  background: 'transparent',
                  height: 40,
                  minHeight: 40,
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault() }
                }}
              />
            </div>
            <div className="flex flex-col items-end gap-1 flex-shrink-0">
              <button
                disabled
                className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 cursor-not-allowed"
                style={{ background: C.border, color: C.muted }}
                title="Human-in-the-loop — coming soon"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 7h12M8 2l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <span className="text-xs whitespace-nowrap" style={{ color: C.muted, fontFamily: 'var(--font-outfit)' }}>HITL — soon</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
