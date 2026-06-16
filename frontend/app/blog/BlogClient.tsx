'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { ArrowUpRight, GitBranch, Layers, Workflow } from 'lucide-react'

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] as const },
})

export default function BlogClient() {
  return (
    <div className="min-h-screen bg-[#FCF1EB] paper-grain">
      {/* Hero Header */}
      <div className="pt-40 pb-24 px-6 max-w-7xl mx-auto">
        <motion.div {...fadeUp(0.1)} className="mb-4">
          <span className="font-mono text-[10px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
            From the Lab
          </span>
        </motion.div>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
          <motion.h1
            {...fadeUp(0.2)}
            className="font-display text-6xl md:text-8xl text-[#3C2F2A] italic leading-[1.0]"
          >
            From the<br />blog.
          </motion.h1>
          <motion.p
            {...fadeUp(0.35)}
            className="font-body text-base text-[#3C2F2A]/60 max-w-sm leading-relaxed pb-2"
          >
            Notes on how AI Research Engineer is actually built — straight from the source,
            no filler.
          </motion.p>
        </div>
      </div>

      {/* Divider */}
      <div className="max-w-7xl mx-auto px-6">
        <div className="h-px bg-[#3C2F2A]/10" />
      </div>

      {/* Featured Post */}
      <div className="max-w-7xl mx-auto px-6 py-20">
        <motion.article {...fadeUp(0.1)} className="group">
          <Link
            href="/blog/architecture-of-ai-research-engineer"
            className="grid md:grid-cols-2 gap-10 md:gap-16 items-center"
          >
            <div className="relative aspect-[4/3] rounded-2xl overflow-hidden shadow-lg">
              <div className="absolute inset-0 bg-gradient-to-br from-[#1a1410] via-[#2c1f18] to-[#1e1612] transition-all duration-700 group-hover:brightness-75" />
              <div className="absolute inset-0 bg-gradient-to-t from-[#3C2F2A]/80 via-[#3C2F2A]/20 to-transparent" />
              <div className="absolute inset-0 grid grid-cols-3 gap-6 place-items-center p-10">
                <Layers className="w-9 h-9 text-white/90 drop-shadow-lg" />
                <Workflow className="w-9 h-9 text-white/90 drop-shadow-lg" />
                <GitBranch className="w-9 h-9 text-white/90 drop-shadow-lg" />
              </div>
              <div className="absolute top-4 left-4">
                <span className="font-mono text-[9px] tracking-[0.3em] uppercase font-bold text-white/80 bg-black/30 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/10">
                  Systems
                </span>
              </div>
              <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <div className="w-8 h-8 rounded-full bg-[#E05240] flex items-center justify-center shadow-lg">
                  <ArrowUpRight className="w-4 h-4 text-white" />
                </div>
              </div>
              <div className="absolute bottom-4 right-4">
                <span className="font-mono text-[9px] tracking-widest uppercase text-white/50">
                  14 min read
                </span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="font-mono text-[9px] tracking-[0.25em] text-[#3C2F2A]/40 uppercase">
                June 16, 2026
              </div>
              <h2 className="font-display text-3xl md:text-5xl text-[#3C2F2A] italic leading-snug group-hover:text-[#E05240] transition-colors duration-300">
                The Architecture of AI Research Engineer
              </h2>
              <p className="font-body text-base text-[#3C2F2A]/60 leading-relaxed">
                How Archimedes turns a hypothesis, paper, dataset, or benchmark into a complete
                reproducible research trace — the agent graph, the three execution modes, the
                evolutionary loop, and everything underneath them.
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {['ADK', 'Claude Code', 'Multi-Agent', 'Architecture'].map((tag) => (
                  <span
                    key={tag}
                    className="font-mono text-[8px] tracking-widest uppercase text-[#3C2F2A]/40 border border-[#3C2F2A]/10 px-2 py-0.5 rounded"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 pt-3 font-body text-sm font-bold text-[#E05240]">
                Read the article
                <ArrowUpRight className="w-4 h-4" />
              </div>
            </div>
          </Link>
        </motion.article>
      </div>

      {/* Bottom CTA */}
      <div className="max-w-7xl mx-auto px-6 pb-24">
        <div className="h-px bg-[#3C2F2A]/10 mb-16" />
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <p className="font-display text-2xl md:text-3xl text-[#3C2F2A]/50 italic">
            More writing as the project grows.
          </p>
          <Link
            href="/docs"
            className="font-body text-xs uppercase tracking-[0.2em] text-[#E05240] border border-[#E05240]/30 px-6 py-2.5 rounded-full hover:bg-[#E05240] hover:text-white transition-all duration-300 font-bold"
          >
            Read the Docs
          </Link>
        </div>
      </div>
    </div>
  )
}
