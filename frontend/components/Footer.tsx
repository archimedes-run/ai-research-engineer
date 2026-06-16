import { Github } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="py-16 px-6 md:px-10 bg-background border-t border-edge">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8">
        {/* Brand */}
        <div>
          <div className="font-brand text-[15px] font-bold tracking-[0.16em] text-ink uppercase mb-1.5">
            archimedes
          </div>
          <div className="font-body text-xs text-ink-dim">
            archimedes.run — Autonomous AI Research Lab
          </div>
        </div>

        {/* Links */}
        <div className="flex items-center gap-8">
          <a
            href="#about"
            className="font-body text-sm text-ink-muted hover:text-ink transition-colors duration-200"
          >
            About
          </a>
          <a
            href="#sessions"
            className="font-body text-sm text-ink-muted hover:text-ink transition-colors duration-200"
          >
            Sessions
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="font-body text-sm text-ink-muted hover:text-ink transition-colors duration-200 flex items-center gap-1.5"
          >
            <Github className="w-4 h-4" />
            GitHub
          </a>
        </div>

        {/* Copyright */}
        <div className="font-brand text-xs text-ink-faint">
          © 2025 Archimedes Research Inc.
        </div>
      </div>
    </footer>
  )
}
