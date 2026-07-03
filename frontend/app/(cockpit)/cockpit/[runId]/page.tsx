'use client'

import { use, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { AnimatePresence, motion } from 'framer-motion'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  ArrowDown, BookOpen, ChevronDown, ChevronRight, Database, Download, Eye, File as FileIco,
  FileCode2, FilePen, FilePlus, FileText, Folder, FolderOpen, Github, Globe, Search,
  Sparkles, Square, Terminal, Wrench, X, Zap,
} from 'lucide-react'
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
interface Session { session_id: string; display_id: string; topic: string; status: string; agent_type: string; research_mode: string; started_at: string; hitl_enabled?: boolean | number; repo_url?: string; github_url?: string }
interface TreeData { stats: { total_nodes: number; by_type: Record<string, number> }; gaps: { reason?: string }[] }

function apiHeaders(): HeadersInit {
  const token = process.env.NEXT_PUBLIC_API_TOKEN
  return token ? { 'X-API-Token': token, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

// ---------------------------------------------------------------------------
// Design tokens — warm light brand theme (everything EXCEPT the Codebase tab)
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
  sidebar: '#F0E9E1',
}

// VS Code Dark+ tokens — the ONE intentionally dark surface (Codebase tab).
// VS.bg is the single "black" constant: change it to #000 in one place.
const VS = {
  bg: '#1E1E1E',        // editor background ("black")
  treeBg: '#181818',    // file tree background
  panel: '#252526',     // tab bar / chrome
  tabInactive: '#2D2D2D',
  text: '#D4D4D4',
  gutter: '#858585',
  border: '#333333',
  fileText: '#E4E4E4',
  fileMuted: '#8A8A8A',
  hoverOrange: '#F5A623',
  brand: '#E05240',
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

// Playful streaming statuses (the app's own curated set)
const GERUNDS = [
  'Ruminating', 'Percolating', 'Noodling', 'Synthesizing', 'Conjuring',
  'Untangling', 'Cogitating', 'Foraging the literature', 'Distilling',
  'Cross-examining', 'Wrangling tensors', 'Sketching the argument',
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

const EXT_TO_LANG: Record<string, string> = {
  py: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript', json: 'json',
  md: 'markdown', sh: 'bash', bash: 'bash', css: 'css', html: 'xml', yaml: 'yaml', yml: 'yaml',
  toml: 'ini', rs: 'rust', go: 'go', tex: 'latex', sql: 'sql', c: 'c', cpp: 'cpp', java: 'java',
}

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

// Humanize a tool call → { Icon, label, summary }
function describeTool(fc: FunctionCallEvent): { Icon: typeof Wrench; label: string; summary: string } {
  const raw = (fc.name ?? 'tool').toLowerCase()
  const args = fc.arguments ?? {}
  const path = typeof args.path === 'string' ? args.path : typeof args.file_path === 'string' ? args.file_path : ''
  const query = typeof args.query === 'string' ? args.query : ''
  const cmd = typeof args.command === 'string' ? args.command : typeof args.cmd === 'string' ? args.cmd : ''
  const pattern = typeof args.pattern === 'string' ? args.pattern : ''
  const firstStr = Object.values(args).find(v => typeof v === 'string') as string | undefined

  let Icon = Wrench
  let label = raw.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  if (raw.includes('semantic_search') || raw.includes('arxiv') || (raw.includes('search') && raw.includes('paper')) || raw.includes('omni_search') || raw.includes('discover')) { Icon = BookOpen; label = 'Search papers' }
  else if (raw.includes('read_paper') || raw.includes('paper_detail') || raw.includes('citation') || raw.includes('reference')) { Icon = BookOpen; label = 'Read paper' }
  else if (raw.includes('download')) { Icon = Download; label = 'Download' }
  else if (raw.includes('duckdb') || raw.includes('query') || raw.includes('sql') || raw.includes('schema')) { Icon = Database; label = 'Query data' }
  else if (raw.includes('compile') && raw.includes('latex')) { Icon = FileText; label = 'Compile PDF' }
  else if (raw.includes('code_context') || raw.includes('code_structure') || raw.includes('blast_radius') || raw.includes('knowledge_graph') || raw.includes('semantically')) { Icon = FileCode2; label = 'Inspect code' }
  else if (raw.includes('directory') || raw.includes('tree') || raw.includes('list_')) { Icon = FolderOpen; label = 'List files' }
  else if (WRITE_TOOLS.has(raw) || (raw.includes('write') && !raw.includes('search'))) { Icon = FilePlus; label = 'Write' }
  else if (raw.includes('edit') || raw.includes('patch')) { Icon = FilePen; label = 'Edit' }
  else if (raw.includes('read') || raw.includes('get_file') || raw.includes('file_info') || raw.includes('media')) { Icon = FileText; label = 'Read' }
  else if (raw.includes('search') || raw.includes('grep') || raw.includes('glob')) { Icon = Search; label = 'Search' }
  else if (raw.includes('bash') || raw.includes('exec') || raw.includes('run') || raw.includes('shell')) { Icon = Terminal; label = 'Run command' }
  else if (raw.includes('fetch') || raw.includes('http') || raw.includes('web')) { Icon = Globe; label = 'Fetch' }

  const summary = path ? path : query ? query : cmd ? cmd : pattern ? pattern : (firstStr ?? fc.name ?? '')
  return { Icon, label, summary }
}

// ---------------------------------------------------------------------------
// Scoped styles — markdown (warm) + highlight themes + editor chrome
// ---------------------------------------------------------------------------
function CockpitStyles() {
  return (
    <style>{`
      /* Warm markdown */
      .md-warm { color: ${C.text}; font-family: var(--font-outfit); font-size: 14px; line-height: 1.72; }
      .md-warm > *:first-child { margin-top: 0 !important; }
      .md-warm > *:last-child { margin-bottom: 0 !important; }
      .md-warm h1 { font-family: var(--font-syne); font-size: 1.5rem; font-weight: 700; margin: 1.1em 0 0.5em; letter-spacing: -0.01em; }
      .md-warm h2 { font-family: var(--font-syne); font-size: 1.22rem; font-weight: 700; margin: 1em 0 0.45em; }
      .md-warm h3 { font-family: var(--font-syne); font-size: 1.02rem; font-weight: 600; margin: 0.9em 0 0.35em; }
      .md-warm p { margin: 0.55em 0; }
      .md-warm ul, .md-warm ol { margin: 0.5em 0; padding-left: 1.35em; }
      .md-warm li { margin: 0.22em 0; }
      .md-warm ul li { list-style: disc; }
      .md-warm ol li { list-style: decimal; }
      .md-warm strong { font-weight: 700; color: ${C.text}; }
      .md-warm em { font-style: italic; }
      .md-warm a { color: ${C.brand}; text-decoration: underline; text-underline-offset: 2px; }
      .md-warm blockquote { border-left: 3px solid ${C.border2}; padding-left: 0.9em; margin: 0.7em 0; color: ${C.muted}; font-style: italic; }
      .md-warm hr { border: none; border-top: 1px solid ${C.border}; margin: 1.1em 0; }
      .md-inline-code { font-family: var(--font-fira-code); font-size: 0.86em; background: ${C.surface2}; color: ${C.brand};
        padding: 0.1em 0.4em; border-radius: 5px; border: 1px solid ${C.border}; }
      .md-warm table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 0.86rem; }
      .md-warm th, .md-warm td { border: 1px solid ${C.border}; padding: 0.42em 0.7em; text-align: left; }
      .md-warm th { background: ${C.surface2}; font-weight: 600; font-family: var(--font-syne); }
      .md-warm tr:nth-child(even) td { background: ${C.surface}; }
      .md-codeblock { font-family: var(--font-fira-code); font-size: 12.5px; line-height: 1.6; margin: 0.75em 0;
        padding: 0.85em 1em; border-radius: 12px; overflow-x: auto; border: 1px solid #E6DED4; background: #FBF6EF; }

      /* highlight.js — warm/light palette (messages + paper) */
      .hljs-warm { color: #453B34; }
      .hljs-warm .hljs-keyword,.hljs-warm .hljs-selector-tag { color: #B0344A; }
      .hljs-warm .hljs-string,.hljs-warm .hljs-attr { color: #6A7A2E; }
      .hljs-warm .hljs-number,.hljs-warm .hljs-literal { color: #B5651D; }
      .hljs-warm .hljs-comment { color: #A79A8E; font-style: italic; }
      .hljs-warm .hljs-function .hljs-title,.hljs-warm .hljs-title.function_ { color: #8A5A2B; }
      .hljs-warm .hljs-title.class_,.hljs-warm .hljs-built_in,.hljs-warm .hljs-type { color: #327361; }
      .hljs-warm .hljs-meta { color: #9B59B6; }
      .hljs-warm .hljs-name,.hljs-warm .hljs-tag { color: #6A7A2E; }
      .hljs-warm .hljs-property { color: #2563EB; }

      /* highlight.js — VS Code Dark+ palette (Codebase editor only) */
      .hljs-vscode { color: ${VS.text}; }
      .hljs-vscode .hljs-keyword,.hljs-vscode .hljs-selector-tag { color: #569CD6; }
      .hljs-vscode .hljs-string { color: #CE9178; }
      .hljs-vscode .hljs-number,.hljs-vscode .hljs-literal { color: #B5CEA8; }
      .hljs-vscode .hljs-comment,.hljs-vscode .hljs-quote { color: #6A9955; font-style: italic; }
      .hljs-vscode .hljs-function .hljs-title,.hljs-vscode .hljs-title.function_,.hljs-vscode .hljs-title { color: #DCDCAA; }
      .hljs-vscode .hljs-class .hljs-title,.hljs-vscode .hljs-title.class_,.hljs-vscode .hljs-type,.hljs-vscode .hljs-built_in { color: #4EC9B0; }
      .hljs-vscode .hljs-attr,.hljs-vscode .hljs-property,.hljs-vscode .hljs-variable { color: #9CDCFE; }
      .hljs-vscode .hljs-meta,.hljs-vscode .hljs-meta .hljs-keyword { color: #C586C0; }
      .hljs-vscode .hljs-name,.hljs-vscode .hljs-tag { color: #569CD6; }
      .hljs-vscode .hljs-operator,.hljs-vscode .hljs-punctuation { color: ${VS.text}; }
      .hljs-vscode .hljs-section,.hljs-vscode .hljs-strong { color: #569CD6; font-weight: 600; }
      .hljs-vscode .hljs-attribute { color: #9CDCFE; }
    `}</style>
  )
}

// ---------------------------------------------------------------------------
// Markdown renderer (warm) — reused by Activity messages + Paper tab
// ---------------------------------------------------------------------------
function WarmCodeBlock({ lang, code }: { lang: string; code: string }) {
  const [html, setHtml] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    import('highlight.js').then(({ default: hljs }) => {
      try {
        const language = EXT_TO_LANG[lang] ?? lang
        const r = language && hljs.getLanguage(language) ? hljs.highlight(code, { language }) : hljs.highlightAuto(code)
        if (alive) setHtml(r.value)
      } catch { if (alive) setHtml(null) }
    }).catch(() => { if (alive) setHtml(null) })
    return () => { alive = false }
  }, [lang, code])
  return (
    <pre className="md-codeblock hljs-warm">
      {html != null ? <code dangerouslySetInnerHTML={{ __html: html }} /> : <code>{code}</code>}
    </pre>
  )
}

const MD_COMPONENTS: Components = {
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className ?? '')
    const text = String(children ?? '').replace(/\n$/, '')
    if (match) return <WarmCodeBlock lang={match[1]} code={text} />
    return <code className="md-inline-code" {...props}>{children}</code>
  },
  pre({ children }) { return <>{children}</> },
  a({ children, href }) { return <a href={href} target="_blank" rel="noreferrer">{children}</a> },
}

function Markdown({ children }: { children: string }) {
  return (
    <div className="md-warm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{children}</ReactMarkdown>
    </div>
  )
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
    <div className="space-y-0.5">
      {STAGES.map((stage, i) => {
        const done = completedStages.has(stage.key)
        const active = !done && activeStage === stage.key && !isTerminal
        return (
          <div key={stage.key} className="flex items-center gap-3">
            <div className="flex flex-col items-center" style={{ width: 18 }}>
              {i > 0 && <div className="w-px mb-1" style={{ height: 10, background: done ? C.green : C.border2 }} />}
              <div className="rounded-full flex items-center justify-center flex-shrink-0"
                style={{
                  width: 15, height: 15, fontSize: 9,
                  background: done ? C.green : active ? C.amber : 'transparent',
                  color: done || active ? '#fff' : C.muted,
                  border: `2px solid ${done ? C.green : active ? C.amber : C.border2}`,
                }}>
                {done ? '✓' : ''}
              </div>
            </div>
            <span className="text-xs py-1"
              style={{ color: done ? C.text : active ? C.amber : C.muted, fontWeight: done || active ? 600 : 400, fontFamily: 'var(--font-outfit)' }}>
              {stage.label}
              {active && <span className="ml-1.5 inline-block w-1 h-1 rounded-full animate-pulse align-middle" style={{ background: C.amber }} />}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent message row (rich markdown)
// ---------------------------------------------------------------------------
function MessageRow({ ev }: { ev: MessageEvent }) {
  const [open, setOpen] = useState(false)
  if (ev.is_thought) return (
    <div className="my-1.5 ml-10">
      <button onClick={() => setOpen(v => !v)} className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md transition-colors hover:bg-black/[0.04]" style={{ color: C.muted }}>
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <Sparkles className="w-3 h-3" style={{ opacity: 0.6 }} /> reasoning
      </button>
      {open && (
        <div className="mt-1 px-3.5 py-2.5 rounded-lg border-l-2 text-xs leading-relaxed" style={{ borderColor: `${C.muted}45`, color: C.muted, background: C.surface2 }}>
          <Markdown>{ev.content}</Markdown>
        </div>
      )}
    </div>
  )
  return (
    <div className="flex gap-3 my-4">
      <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5 shadow-sm"
        style={{ background: `linear-gradient(135deg, ${C.brand}, #C43D2C)`, color: '#fff', fontFamily: 'var(--font-syne)' }}>A</div>
      <div className="flex-1 min-w-0 rounded-2xl px-4 py-3 shadow-sm" style={{ background: C.surface, border: `1px solid ${C.border}` }}>
        <Markdown>{ev.content}</Markdown>
        {ev.is_partial && <span className="inline-block w-1.5 h-3.5 ml-0.5 align-middle animate-pulse rounded-sm" style={{ background: C.brand }} />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tool chips — elegant collapsible group of consecutive tool calls
// ---------------------------------------------------------------------------
function ToolChip({ call, response }: { call: FunctionCallEvent; response?: FunctionResponseEvent }) {
  const [open, setOpen] = useState(false)
  const { Icon, label, summary } = describeTool(call)
  const args = call.arguments ?? {}
  const argStr = JSON.stringify(args, null, 2)
  const respStr = response?.response != null
    ? (typeof response.response === 'string' ? response.response : JSON.stringify(response.response, null, 2))
    : null
  const done = response != null

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: `1px solid ${open ? `${C.brand}35` : C.border}`, background: open ? `${C.brand}05` : 'transparent' }}>
      <button onClick={() => setOpen(v => !v)} className="flex items-center gap-2.5 w-full text-left px-3 py-2 transition-colors hover:bg-black/[0.02]">
        {open ? <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: C.muted }} /> : <ChevronRight className="w-3 h-3 flex-shrink-0" style={{ color: C.muted }} />}
        <Icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: C.brand }} />
        <span className="text-xs font-medium flex-shrink-0" style={{ color: C.text, fontFamily: 'var(--font-outfit)' }}>{label}</span>
        {summary && <span className="text-xs truncate min-w-0" style={{ color: C.muted, fontFamily: 'var(--font-fira-code)', fontSize: 11 }}>{summary}</span>}
        <span className="ml-auto flex-shrink-0">
          {done
            ? <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: C.green }} />
            : <span className="w-1.5 h-1.5 rounded-full inline-block animate-pulse" style={{ background: C.amber }} />}
        </span>
      </button>
      {open && (
        <div className="text-xs" style={{ borderTop: `1px solid ${C.border}` }}>
          {argStr !== '{}' && (
            <div className="px-3.5 py-2.5" style={{ borderBottom: respStr ? `1px solid ${C.border}` : 'none' }}>
              <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: C.muted }}>arguments</div>
              <pre className="overflow-x-auto feed-scroll" style={{ color: C.text, fontFamily: 'var(--font-fira-code)', fontSize: 11, lineHeight: 1.6, margin: 0 }}>{argStr}</pre>
            </div>
          )}
          {respStr && (
            <div className="px-3.5 py-2.5">
              <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: C.muted }}>response</div>
              <pre className="overflow-auto feed-scroll" style={{ color: C.muted, fontFamily: 'var(--font-fira-code)', fontSize: 11, lineHeight: 1.6, margin: 0, maxHeight: 220 }}>{respStr.slice(0, 4000)}{respStr.length > 4000 ? '\n…' : ''}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ToolGroup({ calls }: { calls: { call: FunctionCallEvent; response?: FunctionResponseEvent }[] }) {
  return (
    <div className="my-2.5 ml-10 space-y-1">
      {calls.map((c, i) => <ToolChip key={c.call.seq ?? `tc-${i}`} call={c.call} response={c.response} />)}
    </div>
  )
}

// ---------------------------------------------------------------------------
// HITL card (E.1 — unchanged behavior)
// ---------------------------------------------------------------------------
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
        method: 'POST', headers: apiHeaders(), body: JSON.stringify({ answer: ans }),
      })
      if (r.ok) { setSubmitted(true); onAnswered?.() }
    } finally { setSubmitting(false) }
  }

  if (submitted) return (
    <div className="rounded-xl border px-4 py-3 my-4" style={{ borderColor: `${C.green}40`, background: `${C.green}08` }}>
      <span className="text-xs font-semibold" style={{ color: C.green }}>✓ Response submitted — resuming…</span>
    </div>
  )

  return (
    <div className="rounded-xl border px-4 py-4 my-4 shadow-sm" style={{ borderColor: `${C.amber}45`, background: `${C.amber}08` }}>
      <div className="flex items-center gap-2 mb-3">
        <Eye className="w-3.5 h-3.5" style={{ color: C.amber }} />
        <span className="text-xs tracking-widest uppercase font-semibold" style={{ color: C.amber }}>Awaiting your review</span>
      </div>
      {question && <div className="mb-3"><Markdown>{question}</Markdown></div>}
      {contextMd && (
        <pre className="text-xs rounded-lg p-3 mb-3 border overflow-auto feed-scroll" style={{ borderColor: C.border, background: C.surface, color: C.muted, fontFamily: 'var(--font-fira-code)', whiteSpace: 'pre-wrap', maxHeight: 180 }}>
          {contextMd}
        </pre>
      )}
      {runId && (
        <div className="flex items-center gap-2 mt-1">
          <button onClick={() => submit('approve')} disabled={submitting}
            className="text-xs px-3 py-1.5 rounded-lg border font-medium transition-all flex-shrink-0"
            style={{ borderColor: `${C.green}50`, background: submitting ? 'transparent' : `${C.green}10`, color: submitting ? C.muted : C.green, cursor: submitting ? 'not-allowed' : 'pointer' }}>
            {submitting ? 'Submitting…' : 'Approve & continue'}
          </button>
          <textarea value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Or type feedback…" rows={1} disabled={submitting}
            className="flex-1 text-xs px-3 py-1.5 rounded-lg border outline-none resize-none"
            style={{ borderColor: C.border, background: C.surface, color: C.text, fontFamily: 'var(--font-outfit)', minHeight: 34 }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (answer.trim()) submit(answer.trim()) } }} />
          <button onClick={() => { if (answer.trim()) submit(answer.trim()) }} disabled={!answer.trim() || submitting}
            className="text-xs px-3 py-1.5 rounded-lg border font-medium transition-all flex-shrink-0"
            style={{
              borderColor: answer.trim() && !submitting ? `${C.brand}50` : C.border,
              background: answer.trim() && !submitting ? `${C.brand}10` : 'transparent',
              color: answer.trim() && !submitting ? C.brand : C.muted,
              cursor: answer.trim() && !submitting ? 'pointer' : 'not-allowed',
            }}>
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

// ---------------------------------------------------------------------------
// Playful streaming status
// ---------------------------------------------------------------------------
function StreamingStatus() {
  const [i, setI] = useState(() => Math.floor(Math.random() * GERUNDS.length))
  useEffect(() => {
    const id = setInterval(() => setI(v => (v + 1) % GERUNDS.length), 2400)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="flex items-center gap-3 my-4 ml-10">
      <div className="flex items-center gap-1">
        {[0, 1, 2].map(d => (
          <motion.span key={d} className="w-1.5 h-1.5 rounded-full" style={{ background: C.brand }}
            animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
            transition={{ duration: 1.1, repeat: Infinity, delay: d * 0.18, ease: 'easeInOut' }} />
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.span key={i} className="text-sm italic"
          style={{ color: C.muted, fontFamily: 'var(--font-cormorant)', fontSize: 16 }}
          initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.35 }}>
          {GERUNDS[i]}…
        </motion.span>
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Build grouped feed items from raw events
// ---------------------------------------------------------------------------
type FeedItem =
  | { kind: 'message'; key: string; ev: MessageEvent }
  | { kind: 'stage'; key: string; label: string }
  | { kind: 'hitl'; key: string; ev: HitlEvent }
  | { kind: 'terminal'; key: string; ttype: 'completed' | 'error'; ev: FeedEvent }
  | { kind: 'tools'; key: string; calls: { call: FunctionCallEvent; response?: FunctionResponseEvent }[] }

function buildFeedItems(events: FeedEvent[]): FeedItem[] {
  const items: FeedItem[] = []
  const usedResp = new Set<number>()

  const pushTool = (entry: { call: FunctionCallEvent; response?: FunctionResponseEvent }) => {
    const last = items[items.length - 1]
    if (last && last.kind === 'tools') last.calls.push(entry)
    else items.push({ kind: 'tools', key: `tools-${entry.call.seq ?? items.length}`, calls: [entry] })
  }

  for (let idx = 0; idx < events.length; idx++) {
    const ev = events[idx]
    const key = String(ev.seq ?? `ev-${idx}`)
    if (ev.type === 'keepalive' || ev.type === 'usage') continue

    if (ev.type === 'function_response') {
      if (usedResp.has(idx)) continue
      pushTool({ call: { type: 'function_call', name: (ev as unknown as FunctionResponseEvent).name, arguments: {}, seq: ev.seq } as FunctionCallEvent, response: ev as unknown as FunctionResponseEvent })
      continue
    }
    if (ev.type === 'function_call') {
      const fc = ev as unknown as FunctionCallEvent
      let resp: FunctionResponseEvent | undefined
      for (let j = idx + 1; j < events.length; j++) {
        if (events[j].type === 'function_response' && (events[j] as unknown as FunctionResponseEvent).name === fc.name && !usedResp.has(j)) {
          resp = events[j] as unknown as FunctionResponseEvent; usedResp.add(j); break
        }
      }
      pushTool({ call: fc, response: resp })
      continue
    }
    if (ev.type === 'message') { items.push({ kind: 'message', key, ev: ev as unknown as MessageEvent }); continue }
    if (ev.type === 'hitl_request') { items.push({ kind: 'hitl', key, ev: ev as unknown as HitlEvent }); continue }
    if (ev.type === 'stage') {
      const label = (ev as unknown as StageEvent).stage ?? (ev as unknown as StageEvent).label ?? 'stage'
      items.push({ kind: 'stage', key, label }); continue
    }
    if (ev.type === 'completed') { items.push({ kind: 'terminal', key, ttype: 'completed', ev }); continue }
    if (ev.type === 'error') { items.push({ kind: 'terminal', key, ttype: 'error', ev }); continue }
  }
  return items
}

// ---------------------------------------------------------------------------
// Activity feed — stick-to-bottom + jump pill + refined scroll
// ---------------------------------------------------------------------------
function ActivityFeed({ events, runId, isTerminal, onAnswered }: {
  events: FeedEvent[]; runId: string; isTerminal: boolean; onAnswered: () => void
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickRef = useRef(true)
  const [showPill, setShowPill] = useState(false)
  const items = useMemo(() => buildFeedItems(events), [events])

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior })
  }, [])

  // Initial: jump to bottom on mount
  useEffect(() => { scrollToBottom('auto'); stickRef.current = true }, [scrollToBottom])

  // Stick to bottom as items stream in
  useEffect(() => {
    if (stickRef.current) requestAnimationFrame(() => scrollToBottom('auto'))
  }, [items.length, scrollToBottom])

  const onScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    const near = dist < 80
    stickRef.current = near
    setShowPill(!near)
  }, [])

  return (
    <div className="relative h-full">
      <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto feed-scroll">
        <div className="px-6 py-6 max-w-3xl mx-auto">
          {events.length === 0 && !isTerminal && (
            <div className="flex items-center gap-2 mt-4 text-sm" style={{ color: C.muted }}>
              <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.amber }} />
              Connecting to stream…
            </div>
          )}
          {items.map(item => (
            <motion.div key={item.key} layout="position" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: 'easeOut' }}>
              {item.kind === 'message' && <MessageRow ev={item.ev} />}
              {item.kind === 'tools' && <ToolGroup calls={item.calls} />}
              {item.kind === 'hitl' && <HitlCard ev={item.ev} runId={runId} onAnswered={onAnswered} />}
              {item.kind === 'terminal' && <TerminalBanner type={item.ttype} ev={item.ev} />}
              {item.kind === 'stage' && (
                <div className="flex items-center gap-3 my-5">
                  <div className="flex-1 h-px" style={{ background: C.border2 }} />
                  <span className="text-xs tracking-widest uppercase px-2" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>{item.label}</span>
                  <div className="flex-1 h-px" style={{ background: C.border2 }} />
                </div>
              )}
            </motion.div>
          ))}
          {!isTerminal && events.length > 0 && <StreamingStatus />}
        </div>
      </div>

      <AnimatePresence>
        {showPill && (
          <motion.button
            initial={{ opacity: 0, y: 10, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 10, scale: 0.9 }}
            onClick={() => { scrollToBottom('smooth'); stickRef.current = true; setShowPill(false) }}
            className="absolute left-1/2 -translate-x-1/2 bottom-5 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full shadow-lg text-xs font-medium"
            style={{ background: C.brand, color: '#fff', fontFamily: 'var(--font-outfit)' }}>
            <ArrowDown className="w-3.5 h-3.5" /> Jump to latest
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Paper viewer — compiled PDF if available, else markdown/tex source
// ---------------------------------------------------------------------------
const PAPER_EXTS = new Set(['md', 'tex', 'txt'])

function PaperViewer({ runId, isTerminal }: { runId: string; isTerminal: boolean }) {
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [paperContent, setPaperContent] = useState<string | null>(null)
  const [paperPath, setPaperPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let currentBlobUrl: string | null = null
    async function checkPdf() {
      const res = await fetch(apiUrl(`/api/sessions/${runId}/paper.pdf`), { headers: apiHeaders() }).catch(() => null)
      if (cancelled || !res?.ok) return
      const blob = await res.blob().catch(() => null)
      if (cancelled || !blob) return
      if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl)
      currentBlobUrl = URL.createObjectURL(blob)
      setPdfBlobUrl(currentBlobUrl)
      setLoading(false)
    }
    checkPdf()
    if (isTerminal) return () => { cancelled = true; if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl) }
    const id = setInterval(checkPdf, 10000)
    return () => { cancelled = true; clearInterval(id); if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl) }
  }, [runId, isTerminal])

  const fetchPaper = useCallback(async () => {
    if (pdfBlobUrl) return
    const res = await fetch(apiUrl(`/api/sessions/${runId}/files`), { headers: apiHeaders() }).catch(() => null)
    if (!res?.ok) return
    const tree = await res.json().catch(() => [])
    type NodeLike = { path: string; type: string; children?: NodeLike[] }
    function findCandidates(nodes: NodeLike[]): string[] {
      const results: string[] = []
      for (const n of nodes) {
        if (n.type === 'file' && PAPER_EXTS.has(fileExt(n.path))) results.push(n.path)
        else if (n.children) results.push(...findCandidates(n.children))
      }
      return results
    }
    const sorted = findCandidates(tree).sort((a, b) => {
      const score = (p: string) => p.includes('manuscript') ? 0 : (p.includes('knowledge_base') || p.includes('literature')) ? 1 : p.includes('results') ? 2 : 3
      return score(a) - score(b)
    })
    if (sorted.length === 0) { setLoading(false); return }
    const path = sorted[0]
    const fc = await fetch(apiUrl(`/api/sessions/${runId}/files/${path}`), { headers: apiHeaders() }).catch(() => null)
    if (!fc?.ok) { setLoading(false); return }
    const data = await fc.json().catch(() => null)
    if (data?.content) { setPaperContent(data.content); setPaperPath(path) }
    setLoading(false)
  }, [runId, pdfBlobUrl])

  useEffect(() => {
    fetchPaper()
    if (isTerminal) return
    const id = setInterval(fetchPaper, 5000)
    return () => clearInterval(id)
  }, [isTerminal, fetchPaper])

  if (loading) return <div className="flex items-center justify-center h-full text-sm" style={{ color: C.muted }}>Loading research output…</div>

  if (pdfBlobUrl) return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-2 border-b flex-shrink-0 text-xs" style={{ borderColor: C.border, color: C.muted, background: C.surface }}>
        <span className="font-mono">results/final_research_paper.pdf</span>
        <a href={pdfBlobUrl} download="research_paper.pdf" className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-colors hover:bg-black/[0.03]" style={{ borderColor: C.border, color: C.text }}>
          <Download className="w-3.5 h-3.5" /> Download PDF
        </a>
      </div>
      <iframe src={pdfBlobUrl} className="flex-1 w-full border-0" title="Research Paper PDF" />
    </div>
  )

  if (!paperContent) return (
    <div className="flex flex-col items-center justify-center h-full gap-3" style={{ color: C.muted }}>
      <p className="text-sm">No research output yet — the agent is still working.</p>
      {!isTerminal && <p className="text-xs">This panel refreshes automatically.</p>}
    </div>
  )

  return (
    <div className="h-full overflow-y-auto feed-scroll">
      {paperPath && (
        <div className="px-8 py-2 text-xs border-b sticky top-0 font-mono" style={{ borderColor: C.border, color: C.muted, background: C.surface }}>
          {paperPath} <span className="italic">(source — PDF not yet compiled)</span>
        </div>
      )}
      <article className="max-w-3xl mx-auto px-8 py-10"><Markdown>{paperContent}</Markdown></article>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Codebase tab — dark VS Code-style editor (the ONE dark surface)
// ---------------------------------------------------------------------------
function TreeFileIcon({ path, open }: { path?: string; open?: boolean }) {
  if (path === undefined) return open ? <FolderOpen className="w-3.5 h-3.5" /> : <Folder className="w-3.5 h-3.5" />
  const ext = fileExt(path)
  if (['py'].includes(ext)) return <FileCode2 className="w-3.5 h-3.5" style={{ color: '#4EC9B0' }} />
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext)) return <FileCode2 className="w-3.5 h-3.5" style={{ color: '#569CD6' }} />
  if (['md', 'txt'].includes(ext)) return <FileText className="w-3.5 h-3.5" style={{ color: VS.fileMuted }} />
  if (['json', 'yaml', 'yml', 'toml'].includes(ext)) return <FileCode2 className="w-3.5 h-3.5" style={{ color: '#B5CEA8' }} />
  if (ext === 'tex') return <FileText className="w-3.5 h-3.5" style={{ color: '#CE9178' }} />
  return <FileIco className="w-3.5 h-3.5" style={{ color: VS.fileMuted }} />
}

function DarkTreeNode({ node, expanded, onToggle, onOpen, activeFile, depth }: {
  node: FileNode; expanded: Set<string>; onToggle: (p: string) => void; onOpen: (p: string) => void; activeFile: string | null; depth: number
}) {
  const [hover, setHover] = useState(false)
  const name = fileName(node.path)
  const pad = depth * 12 + 8

  if (node.type === 'dir') {
    const isOpen = expanded.has(node.path)
    return (
      <div>
        <button onClick={() => onToggle(node.path)} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
          className="flex items-center gap-1.5 w-full text-left py-[3px] text-xs transition-colors"
          style={{ paddingLeft: pad, color: hover ? VS.hoverOrange : VS.fileText, background: hover ? 'rgba(245,166,35,0.06)' : 'transparent' }}>
          {isOpen ? <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: VS.fileMuted }} /> : <ChevronRight className="w-3 h-3 flex-shrink-0" style={{ color: VS.fileMuted }} />}
          <TreeFileIcon open={isOpen} />
          <span className="truncate" style={{ fontFamily: 'var(--font-outfit)' }}>{name}</span>
        </button>
        {isOpen && node.children?.map(c => <DarkTreeNode key={c.path} node={c} expanded={expanded} onToggle={onToggle} onOpen={onOpen} activeFile={activeFile} depth={depth + 1} />)}
      </div>
    )
  }
  const isActive = activeFile === node.path
  const color = isActive ? VS.brand : hover ? VS.hoverOrange : VS.fileText
  const bg = isActive ? 'rgba(224,82,64,0.14)' : hover ? 'rgba(245,166,35,0.06)' : 'transparent'
  return (
    <button onClick={() => onOpen(node.path)} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      className="flex items-center gap-1.5 w-full text-left py-[3px] text-xs transition-colors" title={node.path}
      style={{ paddingLeft: pad + 16, color, background: bg }}>
      <TreeFileIcon path={node.path} />
      <span className="truncate" style={{ fontFamily: 'var(--font-outfit)' }}>{name}</span>
    </button>
  )
}

function CodeEditor({ file }: { file: FileContent | null }) {
  const [html, setHtml] = useState<string | null>(null)
  useEffect(() => {
    if (!file?.content) { setHtml(null); return }
    let alive = true
    const lang = EXT_TO_LANG[fileExt(file.path)]
    import('highlight.js').then(({ default: hljs }) => {
      try {
        const r = lang && hljs.getLanguage(lang) ? hljs.highlight(file.content!, { language: lang }) : hljs.highlightAuto(file.content!)
        if (alive) setHtml(r.value)
      } catch { if (alive) setHtml(null) }
    }).catch(() => { if (alive) setHtml(null) })
    return () => { alive = false }
  }, [file])

  const placeholder = (msg: string) => (
    <div className="flex items-center justify-center h-full text-sm" style={{ color: VS.fileMuted, background: VS.bg }}>{msg}</div>
  )
  if (!file) return placeholder('Select a file from the tree to open it')
  if (file.binary) return placeholder('Binary file — no preview available')
  if (file.too_large) return placeholder('File too large to preview')

  const lineCount = (file.content ?? '').split('\n').length
  return (
    <div className="h-full overflow-auto code-scroll" style={{ background: VS.bg }}>
      {file.redacted && (
        <div className="px-4 py-1.5 text-xs sticky top-0 z-10" style={{ background: 'rgba(176,112,16,0.18)', color: '#E2B15A', borderBottom: `1px solid ${VS.border}` }}>⚠ Secrets redacted</div>
      )}
      <div style={{ display: 'flex', minWidth: 'max-content', minHeight: '100%' }}>
        <div className="select-none flex-shrink-0" style={{ position: 'sticky', left: 0, background: VS.bg, borderRight: `1px solid ${VS.border}`, padding: '12px 14px 12px 18px', textAlign: 'right', zIndex: 5 }}>
          {Array.from({ length: lineCount }).map((_, i) => (
            <div key={i} style={{ color: VS.gutter, fontFamily: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace', fontSize: 12.5, lineHeight: 1.5 }}>{i + 1}</div>
          ))}
        </div>
        <pre className="hljs-vscode" style={{ margin: 0, padding: '12px 18px', fontFamily: '"JetBrains Mono", "SF Mono", Menlo, Consolas, monospace', fontSize: 12.5, lineHeight: 1.5, whiteSpace: 'pre', color: VS.text }}>
          {html != null ? <code dangerouslySetInnerHTML={{ __html: html }} /> : <code>{file.content}</code>}
        </pre>
      </div>
    </div>
  )
}

function CodebaseTab({ runId, isTerminal, editingPath, session }: {
  runId: string; isTerminal: boolean; editingPath: string | null; session: Session | null
}) {
  const [fileTree, setFileTree] = useState<FileNode[] | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [openFiles, setOpenFiles] = useState<string[]>([])
  const [activeFile, setActiveFile] = useState<string | null>(null)
  const [cache, setCache] = useState<Record<string, FileContent>>({})
  const [followAgent, setFollowAgent] = useState(true)

  const repoUrl = session?.repo_url ?? session?.github_url ?? null

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
    const id = setInterval(fetchTree, 2500)
    return () => clearInterval(id)
  }, [isTerminal, fetchTree])

  const loadContent = useCallback(async (path: string) => {
    if (cache[path]) return
    const r = await fetch(apiUrl(`/api/sessions/${runId}/files/${path}`), { headers: apiHeaders() }).catch(() => null)
    if (!r?.ok) return
    const d: FileContent | null = await r.json().catch(() => null)
    if (d) setCache(prev => ({ ...prev, [path]: d }))
  }, [runId, cache])

  const openFile = useCallback((path: string, fromAgent = false) => {
    if (!fromAgent) setFollowAgent(false)
    setOpenFiles(prev => prev.includes(path) ? prev : [...prev, path])
    setActiveFile(path)
    loadContent(path)
  }, [loadContent])

  const closeFile = useCallback((path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setOpenFiles(prev => {
      const idx = prev.indexOf(path)
      const next = prev.filter(p => p !== path)
      setActiveFile(cur => {
        if (cur !== path) return cur
        if (next.length === 0) return null
        return next[Math.min(idx, next.length - 1)]
      })
      return next
    })
  }, [])

  // Follow the agent — open/focus a tab as it edits
  useEffect(() => {
    if (!followAgent || !editingPath) return
    openFile(editingPath, true)
  }, [followAgent, editingPath, openFile])

  return (
    <div className="flex h-full overflow-hidden" style={{ background: VS.bg }}>
      {/* File tree */}
      <div className="w-60 flex-shrink-0 flex flex-col" style={{ background: VS.treeBg, borderRight: `1px solid ${VS.border}` }}>
        <div className="flex items-center justify-between px-3 h-9 flex-shrink-0" style={{ borderBottom: `1px solid ${VS.border}` }}>
          <span className="text-xs uppercase tracking-wider" style={{ color: VS.fileMuted, fontFamily: 'var(--font-syne)' }}>Explorer</span>
          <button onClick={() => setFollowAgent(v => !v)} className="text-[10px] px-1.5 py-0.5 rounded transition-colors"
            style={{ color: followAgent ? VS.hoverOrange : VS.fileMuted, border: `1px solid ${followAgent ? 'rgba(245,166,35,0.4)' : VS.border}` }}
            title="Auto-open files as the agent edits them">
            {followAgent ? '● follow' : '○ follow'}
          </button>
        </div>
        <div className="flex-1 overflow-auto code-scroll py-1">
          {fileTree === null ? <div className="px-3 py-2 text-xs" style={{ color: VS.fileMuted }}>Loading…</div>
            : fileTree.length === 0 ? <div className="px-3 py-2 text-xs" style={{ color: VS.fileMuted }}>No files yet</div>
              : fileTree.map(n => (
                <DarkTreeNode key={n.path} node={n} expanded={expandedDirs} activeFile={activeFile} depth={0}
                  onToggle={p => setExpandedDirs(prev => { const next = new Set(prev); if (next.has(p)) next.delete(p); else next.add(p); return next })}
                  onOpen={openFile} />
              ))}
        </div>
      </div>

      {/* Editor pane */}
      <div className="flex-1 flex flex-col overflow-hidden" style={{ background: VS.bg }}>
        {/* Tab bar + GitHub slot */}
        <div className="flex items-stretch h-9 flex-shrink-0" style={{ background: VS.panel, borderBottom: `1px solid ${VS.border}` }}>
          <div className="flex items-stretch overflow-x-auto code-scroll flex-1 min-w-0">
            {openFiles.length === 0 && (
              <div className="flex items-center px-4 text-xs" style={{ color: VS.fileMuted, fontFamily: 'var(--font-outfit)' }}>No files open</div>
            )}
            {openFiles.map(path => {
              const active = activeFile === path
              return (
                <div key={path} onClick={() => setActiveFile(path)}
                  className="group flex items-center gap-2 px-3 cursor-pointer flex-shrink-0 relative"
                  style={{ background: active ? VS.bg : VS.tabInactive, color: active ? VS.fileText : VS.fileMuted, borderRight: `1px solid ${VS.border}`, maxWidth: 200 }}>
                  {active && <span className="absolute top-0 left-0 right-0 h-0.5" style={{ background: VS.brand }} />}
                  <TreeFileIcon path={path} />
                  <span className="text-xs truncate" style={{ fontFamily: 'var(--font-outfit)' }}>{fileName(path)}</span>
                  <button onClick={e => closeFile(path, e)} className="flex-shrink-0 rounded p-0.5 opacity-50 hover:opacity-100 transition-opacity" style={{ color: 'currentColor' }}>
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )
            })}
          </div>
          <div className="flex items-center px-3 flex-shrink-0" style={{ borderLeft: `1px solid ${VS.border}` }}>
            {repoUrl ? (
              <a href={repoUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs transition-colors" style={{ color: VS.fileMuted }}
                onMouseEnter={e => (e.currentTarget.style.color = VS.hoverOrange)} onMouseLeave={e => (e.currentTarget.style.color = VS.fileMuted)}>
                <Github className="w-3.5 h-3.5" /> View on GitHub
              </a>
            ) : (
              <span className="flex items-center gap-1.5 text-xs" style={{ color: VS.fileMuted, opacity: 0.6 }} title="Publishing to GitHub arrives in Phase G">
                <Github className="w-3.5 h-3.5" /> Not published
              </span>
            )}
          </div>
        </div>

        {/* Active editor */}
        <div className="flex-1 overflow-hidden">
          <CodeEditor file={activeFile ? cache[activeFile] ?? null : null} />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Knowledge Graph placeholder (E.2)
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
// Inspector tab
// ---------------------------------------------------------------------------
function InspectorTab({ treeData }: { treeData: TreeData | null }) {
  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full feed-scroll">
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
  const seenSeqs = useRef(new Set<number>())
  const lastSeqRef = useRef(0)
  const [sseVersion, setSseVersion] = useState(0)

  const [activeTab, setActiveTab] = useState<Tab>('activity')
  const [editingPath, setEditingPath] = useState<string | null>(null)
  const [chatMsg, setChatMsg] = useState('')

  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [activeStage, setActiveStage] = useState<string | null>('ideation')

  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [liveUsage, setLiveUsage] = useState<UsageTotals>({ input_tokens: 0, cached_input_tokens: 0, output_tokens: 0, cost_usd: 0 })
  const [treeData, setTreeData] = useState<TreeData | null>(null)

  const [startedAt, setStartedAt] = useState<Date | null>(null)
  const [elapsed, setElapsed] = useState(0)

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

  useEffect(() => {
    if (isTerminal || !startedAt) return
    const id = setInterval(() => setElapsed(Date.now() - startedAt.getTime()), 1000)
    return () => clearInterval(id)
  }, [isTerminal, startedAt])

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

    const inferred = inferStageFromEvent(ev)
    if (inferred) {
      setActiveStage(prev => {
        const stageIdx = STAGES.findIndex(s => s.key === inferred)
        const prevIdx = STAGES.findIndex(s => s.key === prev)
        if (stageIdx > prevIdx) {
          setCompletedStages(c => { const next = new Set(c); for (let i = 0; i < stageIdx; i++) next.add(STAGES[i].key); return next })
          return inferred
        }
        return prev
      })
    }

    const ep = extractEditPath(ev)
    if (ep) setEditingPath(ep)

    setEvents(prev => [...prev, ev])
  }, [runId])

  const handleStop = useCallback(async () => {
    if (stopping || isTerminal) return
    setStopping(true)
    try {
      await fetch(apiUrl(`/api/sessions/${runId}/stop`), { method: 'POST', headers: apiHeaders() })
    } catch { /* SSE state update is source of truth */ }
    finally { setStopping(false) }
  }, [runId, stopping, isTerminal])

  const handleAnswered = useCallback(() => { setSseVersion(v => v + 1) }, [])

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
    { id: 'files', label: 'Codebase' },
    { id: 'graph', label: 'Knowledge Graph' },
    { id: 'inspector', label: 'Inspector' },
  ]

  const tabBg = activeTab === 'files' ? VS.bg : activeTab === 'activity' ? C.bg : C.surface

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: C.bg, color: C.text, fontFamily: 'var(--font-outfit)' }}>
      <CockpitStyles />

      {/* ── Left sidebar — stripped + warm ─────────────────────────────── */}
      <aside className="flex flex-col flex-shrink-0 overflow-hidden" style={{ width: 268, background: C.sidebar, borderRight: `1px solid ${C.border}` }}>
        {/* Logo + stop */}
        <div className="px-5 py-4 flex items-center gap-3" style={{ borderBottom: `1px solid ${C.border}` }}>
          <Link href="/cockpit" className="text-xs font-mono tracking-widest uppercase hover:opacity-70 transition-opacity" style={{ color: C.muted }}>← cockpit</Link>
          {!isTerminal && (
            <button onClick={handleStop} disabled={stopping}
              className="ml-auto flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-all flex-shrink-0"
              style={{ borderColor: stopping ? C.border : `${C.brand}50`, background: stopping ? 'transparent' : `${C.brand}08`, color: stopping ? C.muted : C.brand, cursor: stopping ? 'not-allowed' : 'pointer' }}
              title="Stop this run">
              <Square className="w-3 h-3" style={{ fill: 'currentColor' }} />{stopping ? 'Stopping…' : 'Stop'}
            </button>
          )}
        </div>

        {/* Run identity */}
        <div className="px-5 py-4" style={{ borderBottom: `1px solid ${C.border}` }}>
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <StatusBadge status={statusLabel} />
            {session && (session.hitl_enabled ? (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full border" style={{ borderColor: `${C.blue}40`, color: C.blue, background: `${C.blue}08` }}><Eye className="w-3 h-3" />Supervised</span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full border" style={{ borderColor: C.border, color: C.muted }}><Zap className="w-3 h-3" />Auto</span>
            ))}
          </div>
          <p className="text-sm leading-snug" style={{ color: C.text, fontFamily: 'var(--font-outfit)' }}>{session?.topic ?? 'Loading…'}</p>
          <div className="text-xs font-mono mt-2" style={{ color: C.muted }}>{session?.display_id ?? runId.slice(0, 20)}</div>
        </div>

        {/* Cost + usage */}
        <div className="px-5 py-4" style={{ borderBottom: `1px solid ${C.border}` }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs uppercase tracking-wider mb-0.5" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Cost</div>
              <div className="text-lg font-semibold" style={{ color: C.text, fontFamily: 'var(--font-syne)' }}>{displayUsage ? fmtCost(displayUsage.totals.cost_usd) : '—'}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider mb-0.5" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Tokens</div>
              <div className="text-lg font-semibold" style={{ color: C.text, fontFamily: 'var(--font-syne)' }}>{displayUsage ? fmtTokens(displayUsage.totals.input_tokens + displayUsage.totals.output_tokens) : '—'}</div>
            </div>
          </div>
          {!isTerminal && startedAt && (
            <div className="text-xs mt-3 flex items-center gap-1.5" style={{ color: C.muted }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: C.amber }} />
              running · {fmtElapsed(elapsed)}
            </div>
          )}
        </div>

        {/* Progress */}
        <div className="px-5 py-4 flex-1">
          <div className="text-xs uppercase tracking-widest mb-3" style={{ color: C.muted, fontFamily: 'var(--font-syne)' }}>Progress</div>
          <StageProgress completedStages={completedStages} activeStage={activeStage} isTerminal={isTerminal} />
        </div>
      </aside>

      {/* ── Right main area ────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Tab bar (always warm chrome) */}
        <div className="flex items-center px-4 gap-1 flex-shrink-0" style={{ borderBottom: `1px solid ${C.border}`, height: 46, background: C.surface }}>
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} className="px-3.5 py-1.5 text-sm rounded-lg transition-colors"
              style={{ fontFamily: 'var(--font-outfit)', color: activeTab === tab.id ? C.brand : C.muted, background: activeTab === tab.id ? `${C.brand}10` : 'transparent', fontWeight: activeTab === tab.id ? 600 : 400 }}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden" style={{ background: tabBg }}>
          {activeTab === 'activity' && <ActivityFeed events={events} runId={runId} isTerminal={isTerminal} onAnswered={handleAnswered} />}
          {activeTab === 'paper' && <PaperViewer runId={runId} isTerminal={isTerminal} />}
          {activeTab === 'files' && <CodebaseTab runId={runId} isTerminal={isTerminal} editingPath={editingPath} session={session} />}
          {activeTab === 'graph' && <KnowledgeGraphTab />}
          {activeTab === 'inspector' && <InspectorTab treeData={treeData} />}
        </div>

        {/* Chat input (activity tab only) */}
        {activeTab === 'activity' && (
          <div className="flex-shrink-0 px-4 py-3" style={{ borderTop: `1px solid ${C.border}`, background: C.surface }}>
            <div className="max-w-3xl mx-auto flex items-end gap-3">
              <div className="flex-1 rounded-xl border overflow-hidden" style={{ borderColor: C.border, background: C.bg }}>
                <textarea rows={1} value={chatMsg}
                  onChange={e => { setChatMsg(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px` }}
                  placeholder="Send a message to the agent…"
                  className="w-full px-4 py-2.5 text-sm leading-relaxed resize-none outline-none block"
                  style={{ fontFamily: 'var(--font-outfit)', color: C.text, background: 'transparent', height: 40, minHeight: 40 }}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) e.preventDefault() }} />
              </div>
              <div className="flex flex-col items-end gap-1 flex-shrink-0">
                <button disabled className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 cursor-not-allowed" style={{ background: C.border, color: C.muted }} title="Human-in-the-loop — coming soon">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 7h12M8 2l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
                <span className="text-xs whitespace-nowrap" style={{ color: C.muted, fontFamily: 'var(--font-outfit)' }}>HITL — soon</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
