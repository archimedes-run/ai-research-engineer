'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Github, Menu, X } from 'lucide-react'

function DiscordIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
    </svg>
  )
}
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

          <Link
            href="https://discord.gg/NxQDWu3C"
            target="_blank"
            rel="noopener noreferrer"
            className={`font-body text-sm transition-colors duration-200 flex items-center gap-1.5 ${scrolled
                ? 'text-[#5865F2] hover:text-[#4752C4]'
                : 'text-white/80 hover:text-white drop-shadow-sm'
              }`}
          >
            <DiscordIcon className="w-4 h-4" />
            Discord
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
                className="font-body text-base text-[#3C2F2A]/80 hover:text-[#3C2F2A] py-3 border-b border-[#3C2F2A]/8 flex items-center gap-2"
              >
                <Github className="w-4 h-4" />
                GitHub
              </Link>
              <Link
                href="https://discord.gg/NxQDWu3C"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setMenuOpen(false)}
                className="font-body text-base text-[#5865F2] hover:text-[#4752C4] py-3 flex items-center gap-2"
              >
                <DiscordIcon className="w-4 h-4" />
                Discord
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  )
}