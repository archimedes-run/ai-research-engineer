'use client'

import { motion } from 'framer-motion'
import { BookOpen, Github } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import AsciiOverlay from './AsciiOverlay'

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 28 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.9, delay, ease: [0.16, 1, 0.3, 1] },
})

export default function Hero() {
  return (
    <section className="relative w-full h-screen min-h-[800px] flex flex-col justify-center overflow-hidden bg-[#FEF6F1]">

      {/* 1. BASE LAYER: Sunrise Landscape */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/hero-bg.jpg"
          alt="Archimedes Landscape"
          fill
          priority
          className="object-cover object-center"
        />
      </div>

      {/* 2. EFFECT LAYER: Kinetic Matrix */}
      <AsciiOverlay />

      {/* 2.5. SUNGLASSES: Dimmer for white text pop */}
      <div className="absolute inset-0 z-[5] bg-black/15 pointer-events-none" />

      {/* 3. THE REFINED SMOG TRANSITION */}
      {/* Tight height (h-80), but layered for ultimate smoothness */}
      <div className="absolute inset-x-0 bottom-0 z-[12] pointer-events-none h-80">

        {/* Layer 1: The Base Fill (Matches the site background perfectly) */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#FEF6F1] via-[#FEF6F1]/70 to-transparent" />

        {/* Layer 2: The "Smudger" (Backdrop blur focused only at the very bottom) */}
        <div className="absolute inset-x-0 bottom-0 h-40 backdrop-blur-[2px] [mask-image:linear-gradient(to_top,black,transparent)]" />

        {/* Layer 3: Atmospheric Haze (A very faint orange glow to blend the light) */}
        <div className="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-[#FCE9D8]/20 to-transparent opacity-60" />
      </div>

      {/* 4. CONTENT LAYER */}
      <div className="relative z-20 h-full flex flex-col items-center justify-center px-6 mt-16">

        {/* Status badge */}
        <motion.div
          {...fadeUp(0.6)}
          className="mb-8 flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-white/20 bg-black/20 backdrop-blur-md shadow-sm"
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-80" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-brand" />
          </span>
          <span className="font-brand text-[11px] text-white tracking-[0.18em] uppercase font-bold">
            Open-Source Autonomous Research Framework
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          {...fadeUp(0.82)}
          className="font-display text-[clamp(2.6rem,8vw,6.2rem)] text-center text-white leading-[1.05] tracking-tight max-w-5xl mb-7 drop-shadow-[0_4px_15px_rgba(0,0,0,0.4)]"
        >
          An Open-Source
          <br />
          <strong className="font-bold text-white">
            Autonomous
          </strong>{' '}
          AI
          <br />
          Research Framework.
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          {...fadeUp(1.05)}
          className="font-body text-base md:text-lg text-white/95 text-center max-w-[480px] mb-11 leading-relaxed font-medium drop-shadow-[0_2px_15px_rgba(0,0,0,0.6)]"
        >
          From hypothesis to running experiments to a full reproducible trace.
          Watch Archimedes work.
        </motion.p>

        {/* CTA row */}
        <motion.div
          {...fadeUp(1.25)}
          className="flex items-center gap-4 flex-wrap justify-center"
        >
          <Link
            href="/docs"
            className="btn-glow group relative flex items-center gap-2.5 px-8 py-3.5 rounded-full bg-brand text-white font-body font-medium text-sm overflow-hidden cursor-pointer shadow-lg"
          >
            <span className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-all duration-300" />
            <BookOpen className="w-4 h-4 shrink-0" />
            Read the Docs
          </Link>

          <Link
            href="https://github.com/archimedes-run/ai-research-engineer"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 px-8 py-3.5 rounded-full border border-white/20 bg-black/40 text-white font-body font-medium text-sm backdrop-blur-md hover:bg-black/60 transition-all duration-200 cursor-pointer shadow-sm"
          >
            <Github className="w-4 h-4 shrink-0" />
            View GitHub
          </Link>
        </motion.div>
      </div>

    </section>
  )
}