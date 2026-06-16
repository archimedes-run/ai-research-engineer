'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Github, Menu, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const NAV_LINKS = [
  { label: 'About', href: '#about' },
  { label: 'Docs', href: '/docs' },
  { label: 'Blog', href: '/blog' },
]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [menuOpen])

  const dark = scrolled || menuOpen

  return (
    <motion.nav
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.9, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${dark
          ? 'bg-[#FEF6F1]/90 backdrop-blur-xl border-b border-[#EEDFD5] shadow-sm'
          : 'bg-gradient-to-b from-black/50 via-black/20 to-transparent'
        }`}
    >
      <div className="max-w-7xl mx-auto px-6 md:px-10 h-[68px] flex items-center justify-between">

        {/* Wordmark */}
        <Link
          href="/"
          onClick={() => setMenuOpen(false)}
          className={`font-brand text-[15px] font-bold tracking-[0.16em] uppercase select-none transition-colors duration-300 ${dark ? 'text-[#3C2F2A]' : 'text-white drop-shadow-md'
            }`}
        >
          archimedes
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map((item) => (
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

        {/* Mobile menu toggle */}
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          className={`md:hidden p-2 -mr-2 transition-colors duration-300 ${dark ? 'text-[#3C2F2A]' : 'text-white drop-shadow-md'
            }`}
        >
          {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile menu panel */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="md:hidden overflow-hidden bg-[#FEF6F1] border-b border-[#EEDFD5] shadow-sm"
          >
            <div className="flex flex-col px-6 py-4">
              {NAV_LINKS.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  className="font-body text-base text-[#3C2F2A]/80 hover:text-[#3C2F2A] py-3 border-b border-[#3C2F2A]/8 last:border-b-0"
                >
                  {item.label}
                </Link>
              ))}
              <Link
                href="https://github.com/archimedes-run/ai-research-engineer"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setMenuOpen(false)}
                className="font-body text-base text-[#3C2F2A]/80 hover:text-[#3C2F2A] py-3 flex items-center gap-2"
              >
                <Github className="w-4 h-4" />
                GitHub
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  )
}