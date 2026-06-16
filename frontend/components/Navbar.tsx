'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Github } from 'lucide-react'
import { motion } from 'framer-motion'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <motion.nav
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${scrolled
          ? 'bg-[#FEF6F1]/90 backdrop-blur-xl border-b border-[#EEDFD5] shadow-sm'
          : 'bg-gradient-to-b from-black/50 via-black/20 to-transparent'
        }`}
    >
      <div className="max-w-7xl mx-auto px-6 md:px-10 h-[68px] flex items-center justify-between">

        {/* Wordmark */}
        <Link
          href="/"
          className={`font-brand text-[15px] font-bold tracking-[0.16em] uppercase select-none transition-colors duration-300 ${scrolled ? 'text-[#3C2F2A]' : 'text-white drop-shadow-md'
            }`}
        >
          archimedes
        </Link>

        {/* Links */}
        <div className="flex items-center gap-8">
          {[
            { label: 'About', href: '#about' },
            { label: 'Docs', href: '/docs' },
            { label: 'Blog', href: '/blog' },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`font-body text-sm transition-colors duration-200 flex items-center gap-2 ${scrolled
                  ? 'text-[#3C2F2A]/70 hover:text-[#3C2F2A]'
                  : 'text-white/80 hover:text-white drop-shadow-sm'
                }`}
            >
              {item.label}
            </Link>
          ))}

          <Link
            href="https://github.com/archimedes-run/ai-research-engineer"
            target="_blank"
            rel="noopener noreferrer"
            className={`font-body text-sm transition-colors duration-200 flex items-center gap-1.5 ${scrolled
                ? 'text-[#3C2F2A]/70 hover:text-[#3C2F2A]'
                : 'text-white/80 hover:text-white drop-shadow-sm'
              }`}
          >
            <Github className="w-4 h-4" />
            GitHub
          </Link>
        </div>
      </div>
    </motion.nav>
  )
}