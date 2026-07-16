'use client'

import { motion, useScroll, useSpring } from 'framer-motion'

/**
 * A thin reading-progress bar pinned to the very top of the page.
 * Scroll effect #1 — driven by the document scroll position, spring-smoothed
 * so it glides rather than snaps. Palette: terracotta → coral (brand).
 */
export default function ScrollProgress() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    restDelta: 0.001,
  })

  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed top-0 left-0 right-0 z-[60] h-[3px] origin-left bg-gradient-to-r from-[#E05240] via-[#FF6A58] to-[#FF8C7A] shadow-[0_0_12px_rgba(224,82,64,0.5)]"
    />
  )
}
