'use client'

import { motion } from 'framer-motion'
import { BookOpen, Github } from 'lucide-react'

function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  )
}
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

          <Link
            href="https://discord.gg/NxQDWu3C"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 px-8 py-3.5 rounded-full border border-white/20 bg-[#5865F2]/80 text-white font-body font-medium text-sm backdrop-blur-md hover:bg-[#5865F2] transition-all duration-200 cursor-pointer shadow-sm"
          >
            <DiscordIcon className="w-4 h-4 shrink-0" />
            Join Discord
          </Link>
        </motion.div>
      </div>

    </section>
  )
}