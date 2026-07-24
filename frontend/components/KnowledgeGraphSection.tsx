'use client'

import { useRef } from 'react'
import dynamic from 'next/dynamic'
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion'

// WebGL is client-only — never render the Canvas on the server.
const KnowledgeField = dynamic(() => import('./KnowledgeField'), {
  ssr: false,
  loading: () => null,
})

export default function KnowledgeGraphSection() {
  const shouldReduceMotion = useReducedMotion()
  const ref = useRef<HTMLElement>(null)

  // Scroll effect: the 3D field drifts up + fades in as the section scrolls
  // through the viewport, so the graph "assembles" on approach.
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  const fieldY = useTransform(scrollYProgress, [0, 0.5, 1], ['8%', '0%', '-8%'])
  const fieldOpacity = useTransform(scrollYProgress, [0, 0.28, 0.75, 1], [0, 1, 1, 0.35])

  return (
    <section
      ref={ref}
      className="relative overflow-hidden bg-[#FEF6F1] paper-grain border-t border-[#3C2F2A]/10"
    >
      {/* Soft terracotta light bloom behind the graph. */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[70vh] w-[70vh] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(224,82,64,0.14),transparent_65%)] blur-2xl" />

      {/* The live 3D knowledge graph. */}
      <motion.div
        style={{ y: shouldReduceMotion ? 0 : fieldY, opacity: fieldOpacity }}
        className="absolute inset-0 z-0"
      >
        <KnowledgeField />
      </motion.div>

      {/* Fade the graph into the section edges so it melts into the paper. */}
      <div className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-b from-[#FEF6F1] via-transparent to-[#FEF6F1]" />

      {/* Copy. */}
      <div className="relative z-10 mx-auto flex min-h-[78vh] max-w-3xl flex-col items-center justify-center px-6 py-32 text-center">
        <motion.span
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="font-mono text-[10px] font-bold uppercase tracking-[0.3em] text-[#E05240]"
        >
          A living map
        </motion.span>

        <motion.h2
          initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.08 }}
          className="mt-4 font-display text-4xl italic leading-tight text-[#3C2F2A] md:text-6xl"
        >
          Every paper it reads becomes a node.
        </motion.h2>

        <motion.p
          initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.18 }}
          className="mt-6 max-w-xl font-body text-base leading-relaxed text-[#3C2F2A]/75 md:text-lg"
        >
          Archimedes builds a citation graph as it works — connecting prior art,
          novel directions, and the evidence between them. Drag your cursor to
          feel the depth.
        </motion.p>
      </div>
    </section>
  )
}
