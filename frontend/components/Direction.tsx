'use client'

import { motion, useReducedMotion } from 'framer-motion'
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
  { icon: BookOpenCheck, label: 'Final draft' },
  { icon: History, label: 'Replayable session' },
]

export default function Direction() {
  const shouldReduceMotion = useReducedMotion()

  const inputContainerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.07 } },
  }

  const inputCardVariants = {
    hidden: shouldReduceMotion ? { opacity: 0 } : { opacity: 0, x: -16 },
    visible: shouldReduceMotion
      ? { opacity: 1, transition: { duration: 0.3 } }
      : { opacity: 1, x: 0, transition: { duration: 0.4, ease: 'easeOut' as const } },
  }

  const outputContainerVariants = {
    hidden: {},
    visible: {
      transition: {
        delayChildren: shouldReduceMotion ? 0 : 0.35,
        staggerChildren: shouldReduceMotion ? 0.03 : 0.05,
      },
    },
  }

  const outputCardVariants = {
    hidden: shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 12, scale: 0.98 },
    visible: shouldReduceMotion
      ? { opacity: 1, transition: { duration: 0.3 } }
      : { opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: 'easeOut' as const } },
  }

  return (
    <section className="py-28 px-6 bg-[#FEF6F1] paper-grain relative overflow-hidden border-t border-[#3C2F2A]/10">
      <div className="max-w-5xl mx-auto text-center">

        <motion.span
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="font-mono text-[10px] tracking-[0.3em] text-[#E05240] uppercase font-bold"
        >
          What it does
        </motion.span>

        <motion.h2
          initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5, ease: 'easeOut', delay: 0.1 }}
          className="font-display text-4xl md:text-6xl text-[#3C2F2A] italic leading-tight mt-4 mb-6"
        >
          Give Archimedes a hypothesis, paper, dataset, or benchmark.
        </motion.h2>

        <motion.p
          initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5, ease: 'easeOut', delay: 0.2 }}
          className="font-body text-lg md:text-xl text-[#3C2F2A]/80 max-w-3xl mx-auto leading-relaxed mb-16"
        >
          It produces a complete, reproducible research trace — from the first literature
          search to a reproducible draft and the full record behind it.
        </motion.p>

        <div className="grid md:grid-cols-[1fr_auto_1.4fr] gap-8 md:gap-4 items-center">

          {/* Input cards — stagger from left */}
          <motion.div
            variants={inputContainerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
            className="space-y-3"
          >
            {inputs.map((item) => (
              <motion.div
                key={item.label}
                variants={inputCardVariants}
                className="group flex items-center gap-3 bg-white/60 border border-[#3C2F2A]/10 rounded-xl px-5 py-3.5 text-left shadow-sm transition-all duration-150 ease-out hover:-translate-y-0.5 hover:shadow-md hover:border-[#E05240]/30"
              >
                <item.icon className="w-4 h-4 text-[#E05240] shrink-0 transition-transform duration-150 group-hover:scale-110" />
                <span className="font-body text-sm text-[#3C2F2A] font-medium">{item.label}</span>
              </motion.div>
            ))}
          </motion.div>

          {/* Arrow — infinite pulse */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="flex justify-center py-4 md:py-0"
          >
            <div className="rotate-90 md:rotate-0">
              <motion.div
                animate={shouldReduceMotion ? {} : { scale: [1, 1.06, 1] }}
                transition={shouldReduceMotion ? {} : { duration: 2.5, ease: 'easeInOut', repeat: Infinity }}
                className="w-11 h-11 rounded-full bg-[#E05240] flex items-center justify-center shadow-lg"
              >
                <ArrowRight className="w-5 h-5 text-white" />
              </motion.div>
            </div>
          </motion.div>

          {/* Output cards — stagger after inputs */}
          <motion.div
            variants={outputContainerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
            className="grid grid-cols-2 gap-3"
          >
            {outputs.map((item) => (
              <motion.div
                key={item.label}
                variants={outputCardVariants}
                className="group flex items-center gap-2.5 bg-[#3C2F2A] border border-[#3C2F2A] rounded-xl px-4 py-3.5 text-left shadow-md transition-all duration-150 ease-out hover:-translate-y-0.5 hover:shadow-xl hover:border-[#E05240]/40"
              >
                <item.icon className="w-4 h-4 text-[#FF8C7A] shrink-0 transition-transform duration-150 group-hover:scale-110" />
                <span className="font-body text-[13px] text-white font-medium">{item.label}</span>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* CTA buttons */}
        <div className="mt-16 flex items-center justify-center gap-4 flex-wrap">
          <motion.div
            whileHover={shouldReduceMotion ? {} : { y: -2 }}
            transition={{ duration: 0.15 }}
          >
            <Link
              href="/docs"
              className="px-7 py-3 rounded-full bg-[#3C2F2A] text-white font-body font-medium text-sm hover:bg-[#2A201C] transition-colors duration-200 shadow-md hover:shadow-lg inline-block"
            >
              Read the Docs
            </Link>
          </motion.div>
          <motion.div
            whileHover={shouldReduceMotion ? {} : { y: -2 }}
            transition={{ duration: 0.15 }}
          >
            <Link
              href="/blog/architecture-of-ai-research-engineer"
              className="px-7 py-3 rounded-full border border-[#3C2F2A]/20 text-[#3C2F2A] font-body font-medium text-sm hover:bg-[#3C2F2A]/5 transition-colors duration-200 hover:shadow-md inline-block"
            >
              Read the Architecture
            </Link>
          </motion.div>
        </div>

      </div>
    </section>
  )
}
