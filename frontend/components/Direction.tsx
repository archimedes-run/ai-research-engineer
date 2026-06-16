'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'
import {
  Lightbulb,
  FileText,
  Database,
  Trophy,
  Map,
  ClipboardList,
  Code2,
  FlaskConical,
  LineChart,
  AlertTriangle,
  BookOpenCheck,
  History,
  ArrowRight,
} from 'lucide-react'

const inputs = [
  { icon: Lightbulb, label: 'A hypothesis' },
  { icon: FileText, label: 'A paper' },
  { icon: Database, label: 'A dataset' },
  { icon: Trophy, label: 'A benchmark' },
]

const outputs = [
  { icon: Map, label: 'Literature map' },
  { icon: ClipboardList, label: 'Research plan' },
  { icon: Code2, label: 'Working code' },
  { icon: FlaskConical, label: 'Experiments' },
  { icon: LineChart, label: 'Metrics' },
  { icon: AlertTriangle, label: 'Failures' },
  { icon: BookOpenCheck, label: 'Final paper' },
  { icon: History, label: 'Replayable session' },
]

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-80px' },
  transition: { duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] as const },
})

export default function Direction() {
  return (
    <section className="py-28 px-6 bg-[#FEF6F1] paper-grain relative overflow-hidden border-t border-[#3C2F2A]/10">
      <div className="max-w-5xl mx-auto text-center">
        <motion.span
          {...fadeUp(0)}
          className="font-mono text-[10px] tracking-[0.3em] text-[#E05240] uppercase font-bold"
        >
          What it does
        </motion.span>

        <motion.h2
          {...fadeUp(0.1)}
          className="font-display text-4xl md:text-6xl text-[#3C2F2A] italic leading-tight mt-4 mb-10"
        >
          Give Archimedes a hypothesis, paper, dataset, or benchmark.
        </motion.h2>

        <motion.p
          {...fadeUp(0.2)}
          className="font-body text-lg md:text-xl text-[#3C2F2A]/80 max-w-3xl mx-auto leading-relaxed mb-16"
        >
          It produces a complete, reproducible research trace — from the first literature
          search to a finished, citable paper.
        </motion.p>

        <div className="grid md:grid-cols-[1fr_auto_1.4fr] gap-8 md:gap-4 items-center">
          {/* Inputs */}
          <motion.div {...fadeUp(0.25)} className="space-y-3">
            {inputs.map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-3 bg-white/60 border border-[#3C2F2A]/10 rounded-xl px-5 py-3.5 text-left shadow-sm"
              >
                <item.icon className="w-4 h-4 text-[#E05240] shrink-0" />
                <span className="font-body text-sm text-[#3C2F2A] font-medium">{item.label}</span>
              </div>
            ))}
          </motion.div>

          {/* Arrow */}
          <motion.div {...fadeUp(0.35)} className="flex justify-center py-4 md:py-0">
            <div className="w-11 h-11 rounded-full bg-[#E05240] flex items-center justify-center shadow-lg rotate-90 md:rotate-0">
              <ArrowRight className="w-5 h-5 text-white" />
            </div>
          </motion.div>

          {/* Outputs */}
          <motion.div {...fadeUp(0.4)} className="grid grid-cols-2 gap-3">
            {outputs.map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-2.5 bg-[#3C2F2A] border border-[#3C2F2A] rounded-xl px-4 py-3.5 text-left shadow-md"
              >
                <item.icon className="w-4 h-4 text-[#FF8C7A] shrink-0" />
                <span className="font-body text-[13px] text-white font-medium">{item.label}</span>
              </div>
            ))}
          </motion.div>
        </div>

        <motion.div
          {...fadeUp(0.5)}
          className="mt-16 flex items-center justify-center gap-4 flex-wrap"
        >
          <Link
            href="/docs"
            className="px-7 py-3 rounded-full bg-[#3C2F2A] text-white font-body font-medium text-sm hover:bg-[#2A201C] transition-colors duration-200 shadow-md"
          >
            Read the Docs
          </Link>
          <Link
            href="/blog/architecture-of-ai-research-engineer"
            className="px-7 py-3 rounded-full border border-[#3C2F2A]/20 text-[#3C2F2A] font-body font-medium text-sm hover:bg-[#3C2F2A]/5 transition-colors duration-200"
          >
            Read the Architecture
          </Link>
        </motion.div>
      </div>
    </section>
  )
}
