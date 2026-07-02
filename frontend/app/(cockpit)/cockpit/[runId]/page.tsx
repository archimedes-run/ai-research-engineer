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
interface MessageEvent extends BaseEvent {
  type: 'message'
  content: string
  author?: string
  is_thought?: boolean
  is_partial?: boolean
}
interface FunctionCallEvent extends BaseEvent {
  type: 'function_call'
  name: string
  arguments?: Record<string, unknown>
}
interface FunctionResponseEvent extends BaseEvent {
  type: 'function_response'
  name: string
  response?: unknown
}
interface UsageEvent extends BaseEvent {
  type: 'usage'
  model?: string
  usage?: { input_tokens?: number; cached_input_tokens?: number; output_tokens?: number }
}
interface CompletedEvent extends BaseEvent {
  type: 'completed'
  duration?: number
  files_created?: string[]
}
interface ErrorEvent extends BaseEvent {
  type: 'error'
  content: string
}
interface StageEvent extends BaseEvent {
  type: 'stage'
  stage?: string
  label?: string
}
interface HitlEvent extends BaseEvent {
  type: 'hitl_request'
  question?: string
  context_md?: string
  options?: string[]
}

type FeedEvent = {
  type: string
  seq?: number
  timestamp?: string
  [key: string]: unknown
}

interface FileNode {
  path: string
  type: 'file' | 'dir'
  size: number
  children?: FileNode[]
}

interface FileContent {
  path: string
  content?: string
  binary?: boolean
  too_large?: boolean
  size?: number
  redacted?: boolean
}

interface UsageTotals {
  input_tokens: number
  cached_input_tokens: number
  output_tokens: number
  cost_usd: number
}

interface UsageResponse {
  totals: UsageTotals
  by_model: { model: string; input_tokens: number; cached_input_tokens: number; output_tokens: number; cost_usd: number }[]
}

interface Session {
  session_id: string
  display_id: string
  topic: string
  status: 'running' | 'completed' | 'error' | 'interrupted' | 'failed'
  agent_type: string
  research_mode: string
  started_at: string
  completed_at?: string
}

interface TreeData {
  stats: { total_nodes: number; by_type: Record<string, number>; by_status: Record<string, number> }
  gaps: { node_id?: string; reason?: string }[]
}

// ---------------------------------------------------------------------------
// Auth helper — SSE cannot send headers; v1 assumes open stream for local dev
// Phase D will add signed-ticket auth for SSE.
// ---------------------------------------------------------------------------
function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

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
  if (usd < 1) return `$${usd.toFixed(3)}`
  return `$${usd.toFixed(2)}`
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

function fileName(path: string): string {
  return path.split('/').pop() ?? path
}

const WRITE_TOOL_NAMES = new Set([
  'write_file', 'edit_file', 'create_file', 'write', 'edit', 'patch_file', 'save_file',
])

function extractEditPath(ev: FeedEvent): string | null {
  if (ev.type !== 'function_call') return null
  const name = ((ev as unknown as FunctionCallEvent).name ?? '').toLowerCase()
  if (!WRITE_TOOL_NAMES.has(name) && !name.includes('write') && !name.includes('edit')) return null
  const args = (ev as unknown as FunctionCallEvent).arguments ?? {}
  return (args.path ?? args.file_path ?? args.filename ?? null) as string | null
}

// ---------------------------------------------------------------------------
// Design tokens
// ---------------------------------------------------------------------------
const C = {
  bg: '#0C0A09',
  surface: '#161412',
  surface2: '#1E1A17',
  border: 'rgba(240, 230, 219, 0.08)',
  border2: 'rgba(240, 230, 219, 0.14)',
  text: '#F0E6DB',
  muted: '#7A6A5F',
  brand: '#E05240',
  green: '#5DC47A',
  amber: '#E5A44E',
  blue: '#6BA3E8',
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; pulse: boolean }> = {
    running: { label: 'running', color: C.amber, pulse: true },
    completed: { label: 'done', color: C.green, pulse: false },
    error: { label: 'error', color: C.brand, pulse: false },
    failed: { label: 'failed', color: C.brand, pulse: false },
    interrupted: { label: 'stopped', color: C.muted, pulse: false },
  }
  const s = map[status] ?? { label: status, color: C.muted, pulse: false }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-mono px-2 py-0.5 rounded-full border"
      style={{ borderColor: `${s.color}40`, color: s.color, background: `${s.color}10` }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${s.pulse ? 'animate-pulse' : ''}`}
        style={{ background: s.color }}
      />
      {s.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Cost meter
// ---------------------------------------------------------------------------
function CostMeter({ usage }: { usage: UsageResponse | null }) {
  if (!usage) return null
  const { totals, by_model } = usage
  if (!totals || totals.cost_usd === 0) return null
  return (
    <div className="flex items-center gap-3 text-xs font-mono" style={{ color: C.muted }}>
      <span style={{ color: C.text, fontWeight: 600 }}>{fmtCost(totals.cost_usd)}</span>
      <span>{fmtTokens(totals.input_tokens)} in</span>
      {totals.cached_input_tokens > 0 && (
        <span style={{ color: C.blue }}>{fmtTokens(totals.cached_input_tokens)} cached</span>
      )}
      <span>{fmtTokens(totals.output_tokens)} out</span>
      {by_model?.length > 1 && (
        <span className="opacity-60">{by_model.length} models</span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Feed event renderers
// ---------------------------------------------------------------------------

function MessageRow({
  ev,
  index,
  events,
}: {
  ev: MessageEvent
  index: number
  events: FeedEvent[]
}) {
  void index
  void events
  const [open, setOpen] = useState(false)

  if (ev.is_thought) {
    return (
      <div className="my-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-xs px-2 py-1 rounded transition-colors hover:bg-white/5"
          style={{ color: C.muted }}
        >
          <span style={{ fontSize: 8 }}>{open ? '▼' : '▶'}</span>
          <span>reasoning</span>
        </button>
        {open && (
          <div
            className="mt-1 mx-2 px-3 py-2 rounded border-l-2 text-xs leading-relaxed"
            style={{
              borderColor: `${C.muted}40`,
              color: C.muted,
              background: C.surface,
              fontFamily: 'var(--font-outfit)',
            }}
          >
            {ev.content}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex gap-3 my-3">
      <div
        className="w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5"
        style={{ background: `${C.brand}20`, color: C.brand }}
      >
        A
      </div>
      <div
        className="flex-1 text-sm leading-relaxed rounded-xl px-4 py-3"
        style={{ background: C.surface, color: C.text, fontFamily: 'var(--font-outfit)' }}
      >
        {ev.content}
        {ev.is_partial && (
          <span className="inline-block w-1.5 h-3 ml-1 align-middle bg-current animate-pulse rounded-sm" />
        )}
      </div>
    </div>
  )
}

function ToolRow({
  ev,
  index,
  events,
}: {
  ev: FunctionCallEvent
  index: number
  events: FeedEvent[]
}) {
  const [open, setOpen] = useState(false)
  const response = events.slice(index + 1).find(
    (e) => e.type === 'function_response' && (e as unknown as FunctionResponseEvent).name === ev.name,
  ) as unknown as FunctionResponseEvent | undefined

  const args = ev.arguments ?? {}
  const argStr = JSON.stringify(args, null, 2)
  const respStr =
    response?.response != null
      ? typeof response.response === 'string'
        ? response.response
        : JSON.stringify(response.response, null, 2)
      : null

  return (
    <div className="my-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-all w-full text-left"
        style={{
          borderColor: open ? `${C.blue}40` : C.border,
          background: open ? `${C.blue}08` : C.surface,
          color: C.muted,
        }}
      >
        <span style={{ fontSize: 8, color: C.blue }}>{open ? '▼' : '▶'}</span>
        <span
          style={{ color: C.blue, fontFamily: 'var(--font-fira-code)', fontSize: 11 }}
        >
          {ev.name}
        </span>
        {typeof args.path === 'string' && args.path && (
          <span
            className="ml-1 truncate max-w-xs"
            style={{ color: `${C.text}70`, fontSize: 10, fontFamily: 'var(--font-fira-code)' }}
          >
            {args.path}
          </span>
        )}
        {response && (
          <span className="ml-auto" style={{ color: C.green, fontSize: 9 }}>
            ✓
          </span>
        )}
      </button>

      {open && (
        <div
          className="mt-1 mx-2 rounded-lg border text-xs overflow-hidden"
          style={{ borderColor: `${C.blue}20`, background: '#0D1117' }}
        >
          {argStr !== '{}' && (
            <div className="px-3 py-2 border-b" style={{ borderColor: `${C.blue}15` }}>
              <div
                className="text-xs mb-1 uppercase tracking-wider"
                style={{ color: C.muted }}
              >
                args
              </div>
              <pre
                className="overflow-x-auto"
                style={{
                  color: C.text,
                  fontFamily: 'var(--font-fira-code)',
                  fontSize: 11,
                  lineHeight: 1.5,
                }}
              >
                {argStr}
              </pre>
            </div>
          )}
          {respStr && (
            <div className="px-3 py-2">
              <div
                className="text-xs mb-1 uppercase tracking-wider"
                style={{ color: C.muted }}
              >
                response
              </div>
              <pre
                className="overflow-x-auto max-h-40"
                style={{
                  color: `${C.text}90`,
                  fontFamily: 'var(--font-fira-code)',
                  fontSize: 11,
                  lineHeight: 1.5,
                }}
              >
                {respStr.slice(0, 2000)}
                {respStr.length > 2000 ? '\n…' : ''}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StageDivider({ ev }: { ev: StageEvent }) {
  const label = ev.stage ?? ev.label ?? 'stage'
  return (
    <div className="flex items-center gap-3 my-5">
      <div className="flex-1 h-px" style={{ background: C.border2 }} />
      <span
        className="text-xs tracking-widest uppercase px-2"
        style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}
      >
        {label}
      </span>
      <div className="flex-1 h-px" style={{ background: C.border2 }} />
    </div>
  )
}

function HitlCard({ ev }: { ev: HitlEvent }) {
  return (
    <div
      className="rounded-xl border px-4 py-4 my-4"
      style={{ borderColor: `${C.amber}40`, background: `${C.amber}08` }}
    >
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.amber }} />
        <span
          className="text-xs tracking-widest uppercase font-semibold"
          style={{ color: C.amber, fontFamily: 'var(--font-syne)' }}
        >
          Awaiting your input
        </span>
        <span
          className="ml-auto text-xs px-2 py-0.5 rounded border"
          style={{ color: C.muted, borderColor: C.border, fontSize: 10 }}
        >
          answering arrives in Phase C
        </span>
      </div>
      {ev.question && (
        <p className="text-sm mt-2" style={{ color: C.text, fontFamily: 'var(--font-outfit)' }}>
          {ev.question}
        </p>
      )}
      {ev.options && ev.options.length > 0 && (
        <ul className="mt-3 space-y-1">
          {ev.options.map((opt, i) => (
            <li
              key={i}
              className="text-xs px-3 py-1.5 rounded border"
              style={{ color: C.muted, borderColor: C.border, background: C.surface }}
            >
              {opt}
            </li>
          ))}
        </ul>
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
    <div
      className="rounded-xl border px-4 py-3 my-4"
      style={{ borderColor: `${color}40`, background: `${color}08` }}
    >
      <div className="flex items-center gap-3">
        <span
          className="text-sm font-semibold"
          style={{ color, fontFamily: 'var(--font-syne)' }}
        >
          {label}
        </span>
        {detail && (
          <span className="text-xs" style={{ color: C.muted }}>
            {detail}
          </span>
        )}
      </div>
    </div>
  )
}

function FeedRow({
  ev,
  index,
  events,
}: {
  ev: FeedEvent
  index: number
  events: FeedEvent[]
}) {
  if (ev.type === 'message')
    return <MessageRow ev={ev as unknown as MessageEvent} index={index} events={events} />
  if (ev.type === 'function_call')
    return <ToolRow ev={ev as unknown as FunctionCallEvent} index={index} events={events} />
  if (ev.type === 'function_response') {
    const hasPair = events
      .slice(0, index)
      .some(
        (e) =>
          e.type === 'function_call' &&
          (e as unknown as FunctionCallEvent).name === (ev as unknown as FunctionResponseEvent).name,
      )
    if (hasPair) return null
    return (
      <ToolRow
        ev={
          {
            type: 'function_call',
            name: (ev as unknown as FunctionResponseEvent).name,
            arguments: {},
          } as unknown as FunctionCallEvent
        }
        index={index}
        events={events}
      />
    )
  }
  if (ev.type === 'stage') return <StageDivider ev={ev as unknown as StageEvent} />
  if (ev.type === 'hitl_request') return <HitlCard ev={ev as unknown as HitlEvent} />
  if (ev.type === 'completed') return <TerminalBanner type="completed" ev={ev} />
  if (ev.type === 'error') return <TerminalBanner type="error" ev={ev} />
  if (ev.type === 'keepalive' || ev.type === 'usage') return null
  return (
    <div
      className="my-1 px-3 py-1 text-xs rounded border"
      style={{ borderColor: C.border, color: C.muted, background: C.surface }}
    >
      <span className="font-mono">{ev.type}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// File tree
// ---------------------------------------------------------------------------

function FileIcon({ ext }: { ext: string }) {
  const color: Record<string, string> = {
    py: '#3B82F6', ts: '#3B82F6', tsx: '#61DAFB', js: '#F59E0B',
    jsx: '#61DAFB', json: '#10B981', md: '#8B5CF6', sh: '#22C55E',
    yaml: '#F59E0B', yml: '#F59E0B', toml: '#E05240', txt: C.muted,
    css: '#06B6D4', html: '#F97316', rs: '#F97316', go: '#06B6D4',
  }
  const c = color[ext] ?? C.muted
  return (
    <span
      className="w-3.5 h-3.5 rounded-sm flex-shrink-0 flex items-center justify-center"
      style={{ background: `${c}25`, color: c, fontSize: 7, fontWeight: 700 }}
    >
      {ext ? ext[0].toUpperCase() : '·'}
    </span>
  )
}

function FileTreeNode({
  node,
  expanded,
  onToggle,
  onSelect,
  selectedPath,
  editingPath,
  depth,
}: {
  node: FileNode
  expanded: Set<string>
  onToggle: (p: string) => void
  onSelect: (p: string) => void
  selectedPath: string | null
  editingPath: string | null
  depth: number
}) {
  const name = fileName(node.path)

  if (node.type === 'dir') {
    const isOpen = expanded.has(node.path)
    return (
      <div>
        <button
          onClick={() => onToggle(node.path)}
          className="flex items-center gap-1.5 w-full text-left px-2 py-0.5 rounded text-xs hover:bg-white/5 transition-colors"
          style={{ paddingLeft: `${depth * 12 + 8}px`, color: C.muted }}
        >
          <span style={{ fontSize: 7, opacity: 0.6 }}>{isOpen ? '▼' : '▶'}</span>
          <span style={{ fontFamily: 'var(--font-fira-code)' }}>{name}/</span>
        </button>
        {isOpen &&
          node.children?.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              expanded={expanded}
              onToggle={onToggle}
              onSelect={onSelect}
              selectedPath={selectedPath}
              editingPath={editingPath}
              depth={depth + 1}
            />
          ))}
      </div>
    )
  }

  const ext = fileExt(name)
  const isSelected = selectedPath === node.path
  const isEditing = editingPath === node.path

  return (
    <button
      onClick={() => onSelect(node.path)}
      className="flex items-center gap-1.5 w-full text-left px-2 py-0.5 rounded text-xs transition-colors"
      style={{
        paddingLeft: `${depth * 12 + 8}px`,
        background: isSelected ? `${C.brand}18` : 'transparent',
        color: isSelected ? C.text : C.muted,
      }}
      title={node.path}
    >
      <FileIcon ext={ext} />
      <span className="truncate" style={{ fontFamily: 'var(--font-fira-code)' }}>
        {name}
      </span>
      {isEditing && (
        <span className="ml-auto shrink-0" style={{ color: C.amber, fontSize: 10 }}>
          ✎
        </span>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Code viewer (syntax-highlighted via highlight.js, dynamically imported)
// ---------------------------------------------------------------------------

const EXT_TO_LANG: Record<string, string> = {
  py: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
  json: 'json', md: 'markdown', sh: 'bash', bash: 'bash', css: 'css', html: 'xml',
  yaml: 'yaml', yml: 'yaml', toml: 'ini', rs: 'rust', go: 'go', java: 'java',
  cpp: 'cpp', c: 'c', rb: 'ruby', php: 'php', swift: 'swift', kt: 'kotlin',
  tex: 'latex', bib: 'latex', sql: 'sql', xml: 'xml',
}

function CodeViewer({ file }: { file: FileContent | null }) {
  const [highlighted, setHighlighted] = useState<string | null>(null)

  useEffect(() => {
    if (!file?.content) {
      setHighlighted(null)
      return
    }
    const ext = fileExt(file.path)
    const lang = EXT_TO_LANG[ext]
    import('highlight.js')
      .then(({ default: hljs }) => {
        try {
          const result = lang
            ? hljs.highlight(file.content!, { language: lang })
            : hljs.highlightAuto(file.content!)
          setHighlighted(result.value)
        } catch {
          setHighlighted(null)
        }
      })
      .catch(() => setHighlighted(null))
  }, [file])

  if (!file) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-3 text-sm"
        style={{ color: C.muted }}
      >
        <span style={{ fontSize: 28, opacity: 0.3 }}>⊡</span>
        <span>Select a file to view</span>
      </div>
    )
  }
  if (file.binary) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-2 text-sm"
        style={{ color: C.muted }}
      >
        <span style={{ fontSize: 32, opacity: 0.4 }}>⊘</span>
        <span>Binary file</span>
        {file.size != null && <span className="text-xs">{(file.size / 1024).toFixed(1)} KB</span>}
      </div>
    )
  }
  if (file.too_large) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-2 text-sm"
        style={{ color: C.muted }}
      >
        <span style={{ fontSize: 32, opacity: 0.4 }}>◫</span>
        <span>File too large to preview</span>
        {file.size != null && <span className="text-xs">{(file.size / 1024).toFixed(1)} KB</span>}
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto">
      <style>{`
        .hljs{background:transparent;color:#C9D1D9}
        .hljs-keyword{color:#FF7B72}
        .hljs-string{color:#A5D6FF}
        .hljs-number{color:#79C0FF}
        .hljs-comment{color:#8B949E;font-style:italic}
        .hljs-function .hljs-title,.hljs-title.function_{color:#D2A8FF}
        .hljs-class .hljs-title,.hljs-title.class_{color:#FFA657}
        .hljs-built_in{color:#FFA657}
        .hljs-type{color:#79C0FF}
        .hljs-attr{color:#79C0FF}
        .hljs-literal{color:#79C0FF}
        .hljs-meta{color:#8B949E}
        .hljs-tag{color:#7EE787}
        .hljs-name{color:#7EE787}
        .hljs-operator{color:#FF7B72}
        .hljs-punctuation{color:#8B949E}
        .hljs-section{color:#D2A8FF;font-weight:bold}
        .hljs-bullet{color:#79C0FF}
        .hljs-emphasis{font-style:italic}
        .hljs-strong{font-weight:bold}
        .hljs-link{color:#A5D6FF;text-decoration:underline}
        .hljs-selector-tag{color:#7EE787}
        .hljs-selector-class{color:#FFA657}
        .hljs-property{color:#79C0FF}
        .hljs-deletion{background:#3D1F1F}
        .hljs-addition{background:#1F3D1F}
        .hljs-variable{color:#C9D1D9}
        .hljs-params{color:#C9D1D9}
        .hljs-symbol{color:#79C0FF}
        .hljs-regexp{color:#A5D6FF}
      `}</style>
      {file.redacted && (
        <div
          className="px-4 py-1.5 text-xs flex items-center gap-2 border-b sticky top-0"
          style={{ background: `${C.amber}15`, borderColor: `${C.amber}30`, color: C.amber }}
        >
          <span>⚠</span> Secrets redacted from this file
        </div>
      )}
      <pre
        className="p-4 text-xs leading-relaxed overflow-x-auto"
        style={{ fontFamily: 'var(--font-fira-code)', margin: 0 }}
      >
        {highlighted != null ? (
          <code dangerouslySetInnerHTML={{ __html: highlighted }} />
        ) : (
          <code style={{ color: C.text }}>{file.content}</code>
        )}
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inspector strip
// ---------------------------------------------------------------------------
function InspectorStrip({ treeData }: { treeData: TreeData | null }) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-5">
      {/* Argument tree stats */}
      <div>
        <div
          className="text-xs uppercase tracking-widest mb-3"
          style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}
        >
          Argument Tree
        </div>
        {treeData ? (
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between items-center">
              <span style={{ color: C.muted }}>total nodes</span>
              <span className="font-mono" style={{ color: C.text }}>
                {treeData.stats.total_nodes}
              </span>
            </div>
            {Object.entries(treeData.stats.by_type ?? {}).map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span style={{ color: C.muted }}>{k}</span>
                <span className="font-mono" style={{ color: C.text }}>
                  {v}
                </span>
              </div>
            ))}
            {treeData.gaps.length > 0 && (
              <div className="mt-3 pt-3 border-t" style={{ borderColor: C.border }}>
                <div className="text-xs mb-2" style={{ color: C.amber }}>
                  Gaps ({treeData.gaps.length})
                </div>
                {treeData.gaps.slice(0, 5).map((g, i) => (
                  <div key={i} className="text-xs truncate mb-1" style={{ color: C.muted }}>
                    {g.reason ?? g.node_id ?? '—'}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs" style={{ color: C.muted }}>
            Loading…
          </div>
        )}
      </div>

      {/* Connections stub — Phase G */}
      <div
        className="rounded-xl border px-4 py-4 opacity-50"
        style={{ borderColor: C.border }}
      >
        <div className="flex items-center gap-2 mb-2">
          <span
            className="text-xs uppercase tracking-widest"
            style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}
          >
            Connections
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded border ml-auto"
            style={{ color: C.muted, borderColor: C.border, fontSize: 9 }}
          >
            Phase G — coming soon
          </span>
        </div>
        <p className="text-xs" style={{ color: C.muted }}>
          External tool and data-source wiring will appear here.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params)

  const [session, setSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [isTerminal, setIsTerminal] = useState(false)
  const feedEndRef = useRef<HTMLDivElement>(null)
  const seenSeqs = useRef(new Set<number>())

  // Split-pane resize
  const [leftWidth, setLeftWidth] = useState(45)
  const dragging = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Workspace
  const [fileTree, setFileTree] = useState<FileNode[] | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [followAgent, setFollowAgent] = useState(true)
  const [editingPath, setEditingPath] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'files' | 'inspector'>('files')

  // Usage
  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [liveUsage, setLiveUsage] = useState<UsageTotals>({
    input_tokens: 0,
    cached_input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
  })

  // Arg tree
  const [treeData, setTreeData] = useState<TreeData | null>(null)

  // Elapsed
  const [startedAt, setStartedAt] = useState<Date | null>(null)
  const [elapsed, setElapsed] = useState(0)

  // ---------------------------------------------------------------------------
  // Fetch session metadata
  // ---------------------------------------------------------------------------
  useEffect(() => {
    fetch(apiUrl(`/api/sessions/${runId}`), { headers: apiHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Session | null) => {
        if (!d) return
        setSession(d)
        setStartedAt(new Date(d.started_at))
        if (d.status !== 'running') setIsTerminal(true)
      })
      .catch(() => null)
  }, [runId])

  // Elapsed timer
  useEffect(() => {
    if (isTerminal || !startedAt) return
    const id = setInterval(() => setElapsed(Date.now() - startedAt.getTime()), 1000)
    return () => clearInterval(id)
  }, [isTerminal, startedAt])

  // ---------------------------------------------------------------------------
  // Process incoming event
  // ---------------------------------------------------------------------------
  const processEvent = useCallback(
    (ev: FeedEvent) => {
      const seq = ev.seq as number | undefined
      if (seq != null) {
        if (seenSeqs.current.has(seq)) return
        seenSeqs.current.add(seq)
      }
      if (ev.type === 'keepalive') return
      if (ev.type === 'usage') {
        const u = (ev as UsageEvent).usage ?? {}
        setLiveUsage((prev) => ({
          input_tokens: prev.input_tokens + (u.input_tokens ?? 0),
          cached_input_tokens: prev.cached_input_tokens + (u.cached_input_tokens ?? 0),
          output_tokens: prev.output_tokens + (u.output_tokens ?? 0),
          cost_usd: prev.cost_usd,
        }))
        return
      }
      if (ev.type === 'completed' || ev.type === 'error') {
        setIsTerminal(true)
        fetch(apiUrl(`/api/sessions/${runId}/usage`), { headers: apiHeaders() })
          .then((r) => (r.ok ? r.json() : null))
          .then((d: UsageResponse | null) => { if (d) setUsage(d) })
          .catch(() => null)
      }
      const editPath = extractEditPath(ev)
      if (editPath) setEditingPath(editPath)
      setEvents((prev) => [...prev, ev])
    },
    [runId],
  )

  // ---------------------------------------------------------------------------
  // SSE: backfill then live tail
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let es: EventSource | null = null
    let cancelled = false

    async function start() {
      const res = await fetch(apiUrl(`/api/sessions/${runId}/events?after_seq=0`), {
        headers: apiHeaders(),
      }).catch(() => null)
      if (cancelled || !res?.ok) return
      const backfill: FeedEvent[] = await res.json().catch(() => [])
      if (cancelled) return
      let maxSeq = 0
      for (const ev of backfill) {
        processEvent(ev)
        if ((ev.seq ?? 0) > maxSeq) maxSeq = ev.seq ?? 0
      }
      es = new EventSource(apiUrl(`/api/sessions/${runId}/stream?after_seq=${maxSeq}`))
      es.onmessage = (e) => {
        try {
          processEvent(JSON.parse(e.data))
        } catch {
          // ignore parse errors
        }
      }
      es.onerror = () => es?.close()
    }

    start()
    return () => {
      cancelled = true
      es?.close()
    }
  }, [runId, processEvent])

  // Auto-scroll feed
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  // ---------------------------------------------------------------------------
  // File tree poll (1.5s while active)
  // ---------------------------------------------------------------------------
  const fetchFileTree = useCallback(async () => {
    const res = await fetch(apiUrl(`/api/sessions/${runId}/files`), {
      headers: apiHeaders(),
    }).catch(() => null)
    if (!res?.ok) return
    const data: FileNode[] = await res.json().catch(() => [])
    setFileTree(data)
    setExpandedDirs((prev) => {
      if (prev.size > 0) return prev
      const next = new Set(prev)
      for (const n of data) if (n.type === 'dir') next.add(n.path)
      return next
    })
  }, [runId])

  useEffect(() => {
    fetchFileTree()
    if (isTerminal) return
    const id = setInterval(fetchFileTree, 1500)
    return () => clearInterval(id)
  }, [isTerminal, fetchFileTree])

  // ---------------------------------------------------------------------------
  // Argument tree poll (6s while active)
  // ---------------------------------------------------------------------------
  const fetchArgTree = useCallback(async () => {
    const res = await fetch(apiUrl(`/api/sessions/${runId}/tree`), {
      headers: apiHeaders(),
    }).catch(() => null)
    if (!res?.ok) return
    const data: TreeData = await res.json().catch(() => null)
    if (data) setTreeData(data)
  }, [runId])

  useEffect(() => {
    fetchArgTree()
    if (isTerminal) return
    const id = setInterval(fetchArgTree, 6000)
    return () => clearInterval(id)
  }, [isTerminal, fetchArgTree])

  // ---------------------------------------------------------------------------
  // Usage poll (10s while active)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const fetchUsage = async () => {
      const res = await fetch(apiUrl(`/api/sessions/${runId}/usage`), {
        headers: apiHeaders(),
      }).catch(() => null)
      if (!res?.ok) return
      const data: UsageResponse = await res.json().catch(() => null)
      if (data) setUsage(data)
    }
    fetchUsage()
    if (isTerminal) return
    const id = setInterval(fetchUsage, 10000)
    return () => clearInterval(id)
  }, [isTerminal, runId])

  // ---------------------------------------------------------------------------
  // Follow-agent: auto-open the file the agent is editing
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!followAgent || !editingPath) return
    setSelectedPath(editingPath)
    fetch(apiUrl(`/api/sessions/${runId}/files/${editingPath}`), { headers: apiHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: FileContent | null) => { if (d) setFileContent(d) })
      .catch(() => null)
  }, [followAgent, editingPath, runId])

  // ---------------------------------------------------------------------------
  // File selection (manual — disables follow)
  // ---------------------------------------------------------------------------
  const handleSelectFile = useCallback(
    (path: string) => {
      setFollowAgent(false)
      setSelectedPath(path)
      fetch(apiUrl(`/api/sessions/${runId}/files/${path}`), { headers: apiHeaders() })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: FileContent | null) => { if (d) setFileContent(d) })
        .catch(() => null)
    },
    [runId],
  )

  const handleToggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [])

  // ---------------------------------------------------------------------------
  // Resize drag
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setLeftWidth(Math.max(25, Math.min(75, pct)))
    }
    const onUp = () => { dragging.current = false }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [])

  const displayUsage: UsageResponse | null =
    usage ??
    (liveUsage.cost_usd > 0 ? { totals: liveUsage, by_model: [] } : null)

  const statusLabel = session?.status ?? (isTerminal ? 'completed' : 'running')

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: C.bg, color: C.text, fontFamily: 'var(--font-outfit)' }}
    >
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header
        className="flex items-center gap-4 px-5 flex-shrink-0 border-b"
        style={{ borderColor: C.border, height: 48 }}
      >
        <Link
          href="/cockpit"
          className="text-xs font-mono tracking-widest uppercase transition-opacity hover:opacity-70 flex-shrink-0"
          style={{ color: C.muted }}
        >
          ← cockpit
        </Link>

        <div className="flex-1 min-w-0 flex items-center gap-3 overflow-hidden">
          <span className="text-xs font-mono flex-shrink-0" style={{ color: C.muted }}>
            {session?.display_id ?? runId}
          </span>
          {session?.topic && (
            <span className="text-sm truncate" style={{ color: C.text }}>
              {session.topic}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <StatusBadge status={statusLabel} />
          {!isTerminal && startedAt && (
            <span className="text-xs font-mono" style={{ color: C.muted }}>
              {fmtElapsed(elapsed)}
            </span>
          )}
          <CostMeter usage={displayUsage} />
        </div>
      </header>

      {/* ── Split body ─────────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="flex flex-1 overflow-hidden"
        style={{ cursor: dragging.current ? 'col-resize' : 'auto' }}
      >
        {/* Left pane — activity / chat feed */}
        <div
          className="flex flex-col overflow-hidden border-r flex-shrink-0"
          style={{ width: `${leftWidth}%`, borderColor: C.border }}
        >
          <div
            className="px-4 py-2 border-b text-xs uppercase tracking-widest flex-shrink-0 flex items-center"
            style={{ borderColor: C.border, color: C.muted, fontFamily: 'var(--font-syne)', height: 36 }}
          >
            Activity
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-3">
            {events.length === 0 && !isTerminal && (
              <div
                className="flex items-center gap-2 mt-6 text-sm"
                style={{ color: C.muted }}
              >
                <span
                  className="w-2 h-2 rounded-full animate-pulse flex-shrink-0"
                  style={{ background: C.amber }}
                />
                Connecting to stream…
              </div>
            )}
            {events.map((ev, i) => (
              <FeedRow key={ev.seq ?? `ev-${i}`} ev={ev} index={i} events={events} />
            ))}
            <div ref={feedEndRef} />
          </div>
        </div>

        {/* Drag handle */}
        <div
          className="w-1 flex-shrink-0 cursor-col-resize hover:bg-white/10 transition-colors"
          style={{ background: C.border }}
          onMouseDown={() => { dragging.current = true }}
        />

        {/* Right pane — workspace */}
        <div className="flex flex-col flex-1 overflow-hidden min-w-0">
          {/* Tab bar */}
          <div
            className="flex items-center border-b px-2 gap-1 flex-shrink-0"
            style={{ borderColor: C.border, height: 36 }}
          >
            {(['files', 'inspector'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setRightTab(tab)}
                className="px-3 py-1 text-xs rounded uppercase tracking-wider transition-colors"
                style={{
                  fontFamily: 'var(--font-syne)',
                  color: rightTab === tab ? C.text : C.muted,
                  background: rightTab === tab ? C.surface2 : 'transparent',
                }}
              >
                {tab}
              </button>
            ))}

            {rightTab === 'files' && (
              <div className="ml-auto flex items-center gap-3 pr-2 overflow-hidden">
                {editingPath && (
                  <span
                    className="text-xs font-mono truncate max-w-48"
                    style={{ color: C.amber }}
                  >
                    ✎ {fileName(editingPath)}
                  </span>
                )}
                <button
                  onClick={() => setFollowAgent((v) => !v)}
                  className="text-xs px-2 py-0.5 rounded border transition-all flex-shrink-0"
                  style={{
                    borderColor: followAgent ? `${C.green}50` : C.border,
                    color: followAgent ? C.green : C.muted,
                    background: followAgent ? `${C.green}10` : 'transparent',
                  }}
                >
                  {followAgent ? '⬤ follow' : '○ follow'}
                </button>
              </div>
            )}
          </div>

          {rightTab === 'files' ? (
            <div className="flex flex-col flex-1 overflow-hidden">
              {/* File tree — top 38% */}
              <div
                className="overflow-y-auto border-b py-1.5"
                style={{ borderColor: C.border, flexBasis: '38%', flexShrink: 0, overflow: 'auto' }}
              >
                {fileTree === null ? (
                  <div className="px-3 py-2 text-xs" style={{ color: C.muted }}>
                    Loading workspace…
                  </div>
                ) : fileTree.length === 0 ? (
                  <div className="px-3 py-2 text-xs" style={{ color: C.muted }}>
                    No files yet — the agent is starting
                  </div>
                ) : (
                  fileTree.map((node) => (
                    <FileTreeNode
                      key={node.path}
                      node={node}
                      expanded={expandedDirs}
                      onToggle={handleToggleDir}
                      onSelect={handleSelectFile}
                      selectedPath={selectedPath}
                      editingPath={editingPath}
                      depth={0}
                    />
                  ))
                )}
              </div>

              {/* Code viewer — remaining space */}
              <div
                className="flex-1 overflow-hidden"
                style={{ background: '#0D1117', minHeight: 0 }}
              >
                {selectedPath && (
                  <div
                    className="px-4 py-1.5 text-xs font-mono border-b flex items-center gap-2 flex-shrink-0"
                    style={{
                      borderColor: C.border,
                      color: C.muted,
                      background: C.surface,
                    }}
                  >
                    <span style={{ color: C.text }}>{selectedPath}</span>
                    {fileContent?.size != null && (
                      <span className="ml-auto">
                        {(fileContent.size / 1024).toFixed(1)} KB
                      </span>
                    )}
                  </div>
                )}
                <CodeViewer file={fileContent} />
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-hidden">
              <InspectorStrip treeData={treeData} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
