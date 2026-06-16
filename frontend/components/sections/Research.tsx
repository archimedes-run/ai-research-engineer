'use client'

import { motion } from 'framer-motion'
import { ExternalLink, Zap, BookOpen, Send, CheckCircle } from 'lucide-react'

const stats = [
  { label: 'Papers in review', value: '47' },
  { label: 'Experiments run', value: '2,847' },
  { label: 'Venues targeted', value: '12' },
]

const sessions = [
  {
    status: 'Running',
    color: 'bg-orange-500',
    icon: <Zap className="w-3 h-3 text-orange-500" />,
    title: 'Sparse Mixture-of-Experts with Dynamic Routing in Low-Resource Settings',
    id: 'ARC-2026-051',
    meta: 'Experiment 4 of 9',
    time: '11h ago',
    venue: 'ICML 2026',
  },
  {
    status: 'Writing',
    color: 'bg-amber-400',
    icon: <BookOpen className="w-3 h-3 text-amber-500" />,
    title: 'Contrastive Pretraining for Time-Series Anomaly Detection in Biological Systems',
    id: 'ARC-2026-050',
    meta: 'Writing §4 — Results',
    time: '2d ago',
    venue: 'NeurIPS 2026',
  },
  {
    status: 'Submitted',
    color: 'bg-blue-400',
    icon: <Send className="w-3 h-3 text-blue-500" />,
    title: 'Gradient Accumulation Strategies for Sub-Billion Parameter Language Models',
    id: 'ARC-2026-049',
    meta: 'Under Peer Review',
    time: '8d ago',
    venue: 'ACL 2026',
  },
  {
    status: 'Published',
    color: 'bg-brand',
    icon: <CheckCircle className="w-3 h-3 text-[#E05240]" />,
    title: 'Emergent Tool Use in Reinforcement Learning Agents Without Explicit Reward Shaping',
    id: 'ARC-2026-048',
    meta: 'Published on arXiv',
    time: '14d ago',
    venue: 'ICLR 2026',
    isPrimary: true
  },
]

export default function ActiveSessions() {
  return (
    <section id="sessions" className="py-32 px-6 bg-[#FEF6F1] paper-grain relative overflow-hidden">
      <div className="max-w-7xl mx-auto">

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-20">
          <div className="space-y-4">
            <span className="font-mono text-[10px] tracking-[0.3em] text-[#E05240] uppercase font-bold">
              Live Research
            </span>
            <h2 className="font-display text-5xl md:text-7xl text-[#3C2F2A] italic">
              Active sessions.
            </h2>
          </div>

          {/* Stats Grid */}
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
        <div className="border-t border-[#3C2F2A]/10">
          {sessions.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className={`group relative flex flex-col md:flex-row items-start md:items-center py-8 border-b border-[#3C2F2A]/5 transition-all duration-300 hover:bg-white/40 px-4 -mx-4 rounded-xl`}
            >
              {/* Status Column */}
              <div className="w-32 flex items-center gap-3 mb-4 md:mb-0">
                <div className="relative flex h-2 w-2">
                  {s.status === 'Running' && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
                  )}
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${s.color}`} />
                </div>
                <span className="font-body text-[11px] font-bold uppercase tracking-wider text-[#3C2F2A]/60 group-hover:text-[#3C2F2A] transition-colors">
                  {s.status}
                </span>
              </div>

              {/* Title & Info Column */}
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

              {/* Meta Column */}
              <div className="flex items-center gap-8 mt-6 md:mt-0 w-full md:w-auto justify-between md:justify-end">
                <div className="flex items-center gap-2 text-[#3C2F2A]/30">
                  <span className="font-body text-[11px]">{s.time}</span>
                </div>
                <div className="px-3 py-1 rounded bg-[#3C2F2A]/5 font-mono text-[10px] text-[#3C2F2A]/60">
                  {s.venue}
                </div>
                <button className="p-2 text-[#3C2F2A]/20 hover:text-[#E05240] transition-colors">
                  <ExternalLink className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Footer Link */}
        <div className="mt-12 text-center">
          <button className="font-body text-xs uppercase tracking-[0.2em] text-[#3C2F2A]/40 hover:text-[#E05240] transition-colors duration-300 flex items-center gap-2 mx-auto group">
            View all sessions
            <motion.span animate={{ x: [0, 5, 0] }} transition={{ repeat: Infinity, duration: 1.5 }}>
              →
            </motion.span>
          </button>
        </div>
      </div>
    </section>
  )
}