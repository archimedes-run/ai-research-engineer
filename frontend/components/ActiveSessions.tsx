'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { ExternalLink } from 'lucide-react'
import Link from 'next/link'

type ApiSession = {
  session_id: string
  display_id: string
  title: string
  status: string
  domain: string
  research_mode: string
  started_at: string
}

type Session = {
  id: string
  sessionId: string
  title: string
  status: string
  meta: string
  time: string
  venue: string
  isPrimary?: boolean
}

const STATUS_MAP: Record<string, string> = {
  running: 'Running',
  writing: 'Writing',
  completed: 'Published',
  failed: 'Failed',
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  const hours = Math.floor(diff / 3600000)
  const minutes = Math.floor(diff / 60000)
  if (days > 0) return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (minutes > 0) return `${minutes}m ago`
  return 'just now'
}

function transformSession(s: ApiSession): Session {
  return {
    id: s.display_id,
    sessionId: s.session_id,
    title: s.title,
    status: STATUS_MAP[s.status] ?? s.status,
    meta: `${s.research_mode} · ${s.domain.replace(/_/g, ' ')}`,
    time: timeAgo(s.started_at),
    venue: s.domain.replace(/_/g, ' ').toUpperCase(),
  }
}

const stats = [
  { label: 'Papers in review', value: '47' },
  { label: 'Experiments run', value: '2,847' },
  { label: 'Venues targeted', value: '12' },
]

const statusColors: Record<string, string> = {
  Running: 'bg-orange-500',
  Writing: 'bg-amber-400',
  Submitted: 'bg-blue-400',
  Published: 'bg-[#E05240]',
}

export default function ActiveSessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetch('/api/sessions')
      .then(res => res.json())
      .then((data: ApiSession[]) => {
        setSessions(data.map(transformSession))
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))
  }, [])

  return (
    <section id="sessions" className="py-32 px-6 bg-[#FEF6F1] paper-grain relative overflow-hidden">
      <div className="max-w-7xl mx-auto">

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-20">
          <div className="space-y-4">
            <span className="font-mono text-[10px] tracking-[0.3em] text-[#E05240] uppercase font-bold">
              Live Research
            </span>
            <h2 className="font-display text-5xl md:text-7xl text-[#3C2F2A] italic">
              Active sessions.
            </h2>
          </div>

          <div className="flex gap-12 md:gap-20">
            {stats.map((stat) => (
              <div key={stat.label} className="space-y-1 text-right">
                <div className="font-display text-4xl text-[#3C2F2A]">{stat.value}</div>
                <div className="font-body text-[10px] uppercase tracking-widest text-[#3C2F2A]/40">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sessions List */}
        <div className="border-t border-[#3C2F2A]/10 min-h-[300px] flex flex-col">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center py-24">
              <motion.div
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                className="font-mono text-[10px] uppercase tracking-widest text-[#3C2F2A]/40"
              >
                Initializing Research Agent...
              </motion.div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex-1 flex items-center justify-center py-24">
              <div className="text-center space-y-5">
                <div className="font-mono text-[10px] tracking-[0.3em] text-[#3C2F2A]/30 uppercase mb-2">
                  No Active Cycles
                </div>
                <p className="font-display text-2xl text-[#3C2F2A]/40 italic">
                  No active research cycles detected.
                </p>
                <button className="text-[10px] uppercase tracking-[0.2em] text-[#E05240] font-bold border border-[#E05240]/20 px-6 py-2 rounded-full hover:bg-[#E05240] hover:text-white transition-all duration-300 font-mono">
                  Initiate New Hypothesis
                </button>
              </div>
            </div>
          ) : (
            sessions.map((s, i) => (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="group relative flex flex-col md:flex-row items-start md:items-center py-8 border-b border-[#3C2F2A]/5 transition-all duration-300 hover:bg-white/40 px-4 -mx-4 rounded-xl"
              >
                <div className="w-32 flex items-center gap-3 mb-4 md:mb-0">
                  <div className="relative flex h-2 w-2">
                    {s.status === 'Running' && (
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                    )}
                    <span className={`relative inline-flex rounded-full h-2 w-2 ${statusColors[s.status] ?? 'bg-gray-400'}`} />
                  </div>
                  <span className="font-body text-[11px] font-bold uppercase tracking-wider text-[#3C2F2A]/60 group-hover:text-[#3C2F2A] transition-colors">
                    {s.status}
                  </span>
                </div>

                <div className="flex-1 space-y-1.5">
                  <h3 className={`font-body text-base md:text-lg font-medium transition-colors ${s.isPrimary ? 'text-[#E05240]' : 'text-[#3C2F2A]'}`}>
                    {s.title}
                  </h3>
                  <div className="flex items-center gap-4 font-mono text-[10px] text-[#3C2F2A]/40 uppercase tracking-tighter">
                    <span>{s.id}</span>
                    <span className="w-1 h-1 rounded-full bg-[#3C2F2A]/20" />
                    <span>{s.meta}</span>
                  </div>
                </div>

                <div className="flex items-center gap-8 mt-6 md:mt-0 w-full md:w-auto justify-between md:justify-end">
                  <span className="font-body text-[11px] text-[#3C2F2A]/30">{s.time}</span>
                  <div className="px-3 py-1 rounded bg-[#3C2F2A]/5 font-mono text-[10px] text-[#3C2F2A]/60">
                    {s.venue}
                  </div>
                  <Link
                    href={`/sessions/${s.sessionId}`}
                    className="p-2 text-[#3C2F2A]/20 hover:text-[#E05240] transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Link>
                </div>
              </motion.div>
            ))
          )}
        </div>

        {/* Footer link */}
        <div className="mt-12 text-center">
          <Link
            href="/sessions"
            className="font-body text-xs uppercase tracking-[0.2em] text-[#3C2F2A]/40 hover:text-[#E05240] transition-colors duration-300 inline-flex items-center gap-2 group"
          >
            View all sessions
            <motion.span animate={{ x: [0, 5, 0] }} transition={{ repeat: Infinity, duration: 1.5 }}>
              →
            </motion.span>
          </Link>
        </div>
      </div>
    </section>
  )
}
