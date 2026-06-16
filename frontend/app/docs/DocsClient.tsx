'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { ChevronDown } from 'lucide-react'

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] as const },
})

function CodeBlock({ children, label }: { children: string; label?: string }) {
  return (
    <div className="rounded-xl overflow-hidden border border-white/10 shadow-lg bg-[#1E1E1E] my-4">
      {label && (
        <div className="px-4 py-2 border-b border-white/5 bg-[#272727] font-mono text-[10px] uppercase tracking-widest text-white/40">
          {label}
        </div>
      )}
      <pre className="p-5 overflow-x-auto font-mono text-[12.5px] leading-relaxed text-white/85">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string
  eyebrow: string
  title: string
  children: React.ReactNode
}) {
  return (
    <motion.section {...fadeUp(0.05)} id={id} className="py-14 border-b border-[#3C2F2A]/10">
      <span className="font-mono text-[10px] tracking-[0.3em] text-[#E05240] uppercase font-bold">
        {eyebrow}
      </span>
      <h2 className="font-display text-3xl md:text-4xl text-[#3C2F2A] italic mt-3 mb-6">
        {title}
      </h2>
      <div className="font-body text-[15px] text-[#3C2F2A]/80 leading-relaxed space-y-4 max-w-3xl">
        {children}
      </div>
    </motion.section>
  )
}

const toc = [
  { id: 'overview', label: 'Overview' },
  { id: 'install', label: 'Install' },
  { id: 'quickstart', label: 'Quickstart' },
  { id: 'modes', label: 'Execution modes' },
  { id: 'domains', label: 'Research domains' },
  { id: 'vault', label: 'The research vault' },
  { id: 'api', label: 'Python API' },
  { id: 'architecture', label: 'Architecture' },
]

export default function DocsClient() {
  const [tocOpen, setTocOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#FCF1EB] paper-grain overflow-x-hidden">
      {/* Header */}
      <div className="pt-32 md:pt-40 pb-12 md:pb-16 px-4 sm:px-6 max-w-7xl mx-auto">
        <motion.div {...fadeUp(0)} className="mb-4">
          <span className="font-mono text-[10px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
            Documentation
          </span>
        </motion.div>
        <motion.h1
          {...fadeUp(0.1)}
          className="font-display text-4xl sm:text-5xl md:text-7xl text-[#3C2F2A] italic leading-[1.05] max-w-4xl"
        >
          How to run autonomous AI research.
        </motion.h1>
        <motion.p
          {...fadeUp(0.2)}
          className="font-body text-base md:text-lg text-[#3C2F2A]/70 max-w-2xl mt-6 leading-relaxed"
        >
          Give Archimedes a hypothesis, paper, dataset, or benchmark. It produces a complete,
          reproducible research trace: literature map, plan, code, experiments, metrics,
          failures, final paper, and a replayable session — start to finish, with no human in
          the loop.
        </motion.p>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 md:grid md:grid-cols-[200px_1fr] md:gap-12">
        {/* Collapsible index */}
        <aside className="mb-8 md:mb-0">
          {/* Mobile: sticky toggle with floating overlay panel */}
          <div className="md:hidden sticky top-[68px] z-40 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-[#FCF1EB]/95 backdrop-blur-md border-b border-[#3C2F2A]/10">
            <div className="relative">
              <button
                type="button"
                onClick={() => setTocOpen((open) => !open)}
                aria-expanded={tocOpen}
                className="w-full flex items-center justify-between gap-2 font-mono text-[11px] tracking-[0.2em] uppercase text-[#3C2F2A]/70 border border-[#3C2F2A]/15 rounded-xl px-4 py-3 bg-[#FEF6F1]"
              >
                Contents
                <ChevronDown
                  className={`w-4 h-4 shrink-0 transition-transform duration-300 ${tocOpen ? 'rotate-180' : ''}`}
                />
              </button>

              <AnimatePresence>
                {tocOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                    className="absolute left-0 right-0 top-full mt-2 z-40 border border-[#3C2F2A]/15 rounded-xl px-4 py-2 bg-[#FEF6F1] shadow-xl"
                  >
                    {toc.map((item) => (
                      <a
                        key={item.id}
                        href={`#${item.id}`}
                        onClick={() => setTocOpen(false)}
                        className="block font-body text-sm text-[#3C2F2A]/60 hover:text-[#E05240] transition-colors py-2 border-b border-[#3C2F2A]/8 last:border-b-0"
                      >
                        {item.label}
                      </a>
                    ))}
                    <Link
                      href="https://github.com/archimedes-run/ai-research-engineer"
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => setTocOpen(false)}
                      className="block font-body text-sm text-[#E05240] font-medium py-2"
                    >
                      View on GitHub →
                    </Link>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Mobile: backdrop blur over the rest of the page while open */}
          <AnimatePresence>
            {tocOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                onClick={() => setTocOpen(false)}
                className="md:hidden fixed inset-0 z-30 bg-black/10 backdrop-blur-sm"
              />
            )}
          </AnimatePresence>

          {/* Desktop: always-visible sticky list */}
          <div className="hidden md:block sticky top-28 space-y-1">
            {toc.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block font-body text-sm text-[#3C2F2A]/50 hover:text-[#E05240] transition-colors py-1.5"
              >
                {item.label}
              </a>
            ))}
            <Link
              href="https://github.com/archimedes-run/ai-research-engineer"
              target="_blank"
              rel="noopener noreferrer"
              className="block font-body text-sm text-[#E05240] font-medium pt-4"
            >
              View on GitHub →
            </Link>
          </div>
        </aside>

        {/* Content */}
        <div className="pb-24 md:pb-32 min-w-0">
          <Section id="overview" eyebrow="01 // What it is" title="Overview">
            <p>
              <strong>AI Research Engineer</strong> (codename <em>Archimedes</em>) is an
              open-source, multi-agent framework that automates the entire lifecycle of machine
              learning research — from novel hypothesis generation, through literature review
              and experiment design, to working code, empirical validation, and a
              reproducible manuscript and a full audit trail of how it got there.
            </p>
            <p>
              It is built on Google&apos;s Agent Development Kit (ADK) for orchestration and the
              Claude Agent SDK for surgical code implementation. Every run produces an auditable,
              replayable trace of exactly how the agent thought, what it tried, what failed, and
              why it made the decisions it did.
            </p>
          </Section>

          <Section id="install" eyebrow="02 // Setup" title="Install">
            <p>You need the Claude Code CLI and a few API keys before your first run.</p>
            <CodeBlock label="1. install the Claude Code CLI">
{`npm install -g @anthropic-ai/claude-code`}
            </CodeBlock>
            <CodeBlock label="2. clone and install">
{`git clone https://github.com/archimedes-run/ai-research-engineer.git
cd ai-research-engineer
uv sync --extra dev`}
            </CodeBlock>
            <CodeBlock label="3. configure .env">
{`ANTHROPIC_API_KEY="your_key"
OPENROUTER_API_KEY="your_key"
SEMANTIC_SCHOLAR_API_KEY="your_key"   # optional, raises literature search rate limits`}
            </CodeBlock>
          </Section>

          <Section id="quickstart" eyebrow="03 // First run" title="Quickstart">
            <p>
              Run the full multi-agent research lifecycle against a single natural-language
              prompt:
            </p>
            <CodeBlock label="terminal">
{`uv run ai-research-engineer "Investigate Kolmogorov-Arnold Networks \\
  for weather forecasting" --mode orchestrated`}
            </CodeBlock>
            <p>
              By default, output lands in <code className="font-mono text-[#E05240]">./agentic_output/</code>{' '}
              and is preserved after the run. Use <code className="font-mono text-[#E05240]">--temp-dir</code>{' '}
              for an auto-cleaned scratch run, or{' '}
              <code className="font-mono text-[#E05240]">--working-dir &lt;path&gt;</code> to pin a
              custom location.
            </p>
          </Section>

          <Section id="modes" eyebrow="04 // Configuration" title="Execution modes">
            <p>
              <code className="font-mono text-[#E05240]">--mode</code> is required and controls
              how much autonomy the agent is given:
            </p>
            <ul className="list-disc pl-5 space-y-2">
              <li>
                <strong>orchestrated</strong> — the full pipeline: ideation, planning,
                stage-by-stage implementation, reflection, and manuscript synthesis.
              </li>
              <li>
                <strong>simple</strong> — direct Claude Code execution with no planning
                overhead. Faster and cheaper for narrow coding tasks.
              </li>
              <li>
                <strong>evolve</strong> — an autonomous Darwinian optimization loop that samples
                a FAISS database of past attempts, mutates the highest-scoring candidate, and
                keeps what improves the metric.
              </li>
            </ul>
            <p>
              Two more flags shape the run:{' '}
              <code className="font-mono text-[#E05240]">--research-mode novelty|replication</code>{' '}
              toggles between inventing new architectures or strict paper replication, and{' '}
              <code className="font-mono text-[#E05240]">--template</code> picks the LaTeX
              template used for the final manuscript.
            </p>
          </Section>

          <Section id="domains" eyebrow="05 // Context" title="Research domains">
            <p>
              <code className="font-mono text-[#E05240]">--domain</code> injects
              domain-specific planning and review heuristics into every agent in the pipeline.
              Supported domains: <strong>aiml</strong>, <strong>finance</strong>,{' '}
              <strong>bioinformatics</strong>, <strong>algorithms</strong>, and{' '}
              <strong>physics</strong>.
            </p>
          </Section>

          <Section id="vault" eyebrow="06 // Output" title="The research vault">
            <p>
              Every run produces a structured workspace designed to survive long sessions and
              context resets — the agent never has to re-derive what it already learned:
            </p>
            <ul className="list-disc pl-5 space-y-2">
              <li>
                <code className="font-mono text-[#E05240]">knowledge_base/</code> — synthesized
                literature notes and architecture blueprints.
              </li>
              <li>
                <code className="font-mono text-[#E05240]">literature/</code> — raw full-text
                sources pulled from ArXiv and Semantic Scholar.
              </li>
              <li>
                <code className="font-mono text-[#E05240]">workflow/</code> — implementation
                code, training loops, and neural network modules.
              </li>
              <li>
                <code className="font-mono text-[#E05240]">results/</code> — metric logs, model
                checkpoints, and comparison plots.
              </li>
              <li>
                <code className="font-mono text-[#E05240]">manuscript/</code> — the final,
                compiled LaTeX/PDF paper.
              </li>
            </ul>
          </Section>

          <Section id="api" eyebrow="07 // Embedding" title="Python API">
            <p>
              Prefer code to a CLI? The same engine is a plain async-first Python class with a
              streaming event interface — this is exactly what powers the CLI and any backend
              you wire up around it.
            </p>
            <CodeBlock label="python">
{`from ai_research_engineer import AIEngineer

engineer = AIEngineer(
    agent_type="adk",          # "adk" | "claude_code" | "evolve"
    research_mode="novelty",   # "novelty" | "replication"
    domain="ai_ml",
    working_dir="./my_run",
)

result = engineer.run("Investigate sparse mixture-of-experts routing")
print(result.response)
print(result.files_created)`}
            </CodeBlock>
            <p>
              For streaming token-by-token and tool-call events (e.g. to drive a UI),
              call <code className="font-mono text-[#E05240]">await engineer.run_async(prompt, stream=True)</code>{' '}
              and iterate the returned async generator.
            </p>
          </Section>

          <Section id="architecture" eyebrow="08 // Deep dive" title="Architecture">
            <p>
              For a full technical breakdown of the agent graph — the ideation loop, the
              planning loop, the stage orchestrator and reflector, the evolution loop, and the
              paper-writing loop — read the architecture deep dive.
            </p>
            <Link
              href="/blog/architecture-of-ai-research-engineer"
              className="inline-flex items-center gap-2 font-body text-sm font-bold text-white bg-[#E05240] px-6 py-3 rounded-full hover:bg-[#D04130] transition-colors"
            >
              Read the Architecture →
            </Link>
          </Section>
        </div>
      </div>
    </div>
  )
}
