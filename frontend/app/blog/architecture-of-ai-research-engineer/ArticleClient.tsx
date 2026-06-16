'use client'

import { motion } from 'framer-motion'
import Link from 'next/link'

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] as const },
})

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2
      id={id}
      className="font-display text-3xl md:text-4xl text-[#3C2F2A] italic mt-16 mb-6 scroll-mt-24"
    >
      {children}
    </h2>
  )
}

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="font-body text-lg font-bold text-[#3C2F2A] mt-8 mb-3">{children}</h3>
  )
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="font-body text-[16px] text-[#3C2F2A]/80 leading-relaxed mb-4">{children}</p>
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="font-mono text-[13px] text-[#E05240] bg-[#E05240]/[0.08] px-1.5 py-0.5 rounded">
      {children}
    </code>
  )
}

function UL({ children }: { children: React.ReactNode }) {
  return <ul className="list-disc pl-5 space-y-2.5 mb-5 font-body text-[16px] text-[#3C2F2A]/80 leading-relaxed">{children}</ul>
}

function FAQ({ q, a }: { q: string; a: string }) {
  return (
    <div className="border-b border-[#3C2F2A]/10 py-6">
      <h3 className="font-body text-base font-bold text-[#3C2F2A] mb-2">{q}</h3>
      <p className="font-body text-[15px] text-[#3C2F2A]/75 leading-relaxed">{a}</p>
    </div>
  )
}

export default function ArticleClient() {
  return (
    <article className="min-h-screen bg-[#FCF1EB] paper-grain">
      {/* Header */}
      <header className="pt-40 pb-16 px-6 max-w-3xl mx-auto">
        <motion.div {...fadeUp(0)} className="mb-5">
          <span className="font-mono text-[10px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
            Architecture Deep Dive
          </span>
        </motion.div>
        <motion.h1
          {...fadeUp(0.1)}
          className="font-display text-4xl md:text-6xl text-[#3C2F2A] italic leading-[1.08] mb-6"
        >
          The Architecture of AI Research Engineer
        </motion.h1>
        <motion.p {...fadeUp(0.18)} className="font-body text-lg text-[#3C2F2A]/70 leading-relaxed">
          How Archimedes turns a single sentence into a literature review, an experimental plan,
          working code, real metrics, and a finished paper — with no human in the loop.
        </motion.p>
        <motion.div
          {...fadeUp(0.25)}
          className="flex items-center gap-4 mt-6 font-mono text-[11px] uppercase tracking-widest text-[#3C2F2A]/40"
        >
          <span>June 16, 2026</span>
          <span className="w-1 h-1 rounded-full bg-[#3C2F2A]/20" />
          <span>14 min read</span>
          <span className="w-1 h-1 rounded-full bg-[#3C2F2A]/20" />
          <span>Systems</span>
        </motion.div>
      </header>

      <div className="max-w-3xl mx-auto px-6">
        <div className="h-px bg-[#3C2F2A]/10 mb-2" />
      </div>

      {/* Body */}
      <div className="max-w-3xl mx-auto px-6 pb-28">
        {/* TL;DR */}
        <motion.div
          {...fadeUp(0.1)}
          className="bg-[#3C2F2A] text-white rounded-2xl p-7 my-10 shadow-lg"
        >
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#FF8C7A] uppercase font-bold">
            TL;DR
          </span>
          <p className="font-body text-[15px] leading-relaxed mt-3 text-white/90">
            AI Research Engineer is an open-source multi-agent system that automates ML research
            end to end. Google&apos;s Agent Development Kit (ADK) orchestrates planning,
            reflection, and review; Claude (via the Claude Code CLI) handles surgical code
            implementation; a FAISS-backed evolutionary loop can optimize a metric across
            generations; and every run produces an inspectable, replayable trace — literature
            map, plan, code, experiments, metrics, failures, and a compiled paper.
          </p>
        </motion.div>

        <motion.div {...fadeUp(0)}>
          <H2 id="what-is-it">What Is AI Research Engineer?</H2>
          <P>
            <strong>AI Research Engineer</strong> is a framework, not a single model. It is a
            graph of specialized LLM agents — each with a narrow job, a strict prompt, and a
            defined handoff — wired together into a workflow that mirrors how a real research
            lab operates: someone proposes an idea, someone checks it against the literature,
            someone plans the experiments, someone writes the code, someone watches the metrics,
            and someone writes the paper.
          </P>
          <P>
            The project ships under the internal codename <strong>Archimedes</strong>. Give it a
            hypothesis, a paper to replicate, a dataset, or a benchmark to beat, and it runs the
            entire research lifecycle autonomously, leaving behind a full audit trail of how it
            got there.
          </P>

          <H2 id="core-loop">The Core Loop: From Input to Reproducible Trace</H2>
          <P>
            Every invocation accepts one of four input types and produces the same eight-part
            output:
          </P>
          <UL>
            <li><strong>Input:</strong> a hypothesis, a paper, a dataset, or a benchmark.</li>
            <li>
              <strong>Output:</strong> a literature map, a research plan, working code, executed
              experiments, measured metrics, recorded failures, a final paper, and a replayable
              session log.
            </li>
          </UL>
          <P>
            This input/output contract is what makes the system composable: the same engine
            backs the CLI (<Code>ai-research-engineer &quot;…&quot; --mode orchestrated</Code>),
            a plain Python API (<Code>AIEngineer</Code>), and any HTTP service built on top of it.
          </P>

          <H2 id="agent-graph">The Agent Graph in Orchestrated Mode</H2>
          <P>
            In <Code>--mode orchestrated</Code>, the root workflow —{' '}
            <Code>ai_research_engineer_workflow</Code> — runs five phases in sequence, each
            implemented as its own ADK sub-agent or loop agent.
          </P>

          <H3>1. Ideation Loop</H3>
          <P>
            <Code>idea_generator_agent</Code> proposes a hypothesis; <Code>novelty_scorer_agent</Code>{' '}
            checks it against ArXiv and Semantic Scholar and scores it for novelty and
            feasibility. The two run in a loop —{' '}
            <Code>ideation_loop</Code> — with a review-confirmation agent that can send the idea
            back for another pass before the loop exits.
          </P>

          <H3>2. High-Level Planning Loop</H3>
          <P>
            <Code>plan_maker_agent</Code> turns the accepted hypothesis into a milestone-based
            experimental design — baselines, ablations, and concrete success criteria.{' '}
            <Code>plan_reviewer_agent</Code> critiques it inside{' '}
            <Code>high_level_planning_loop</Code> until the plan is sound, and{' '}
            <Code>high_level_plan_parser</Code> converts the approved plan into discrete,
            machine-readable stages.
          </P>

          <H3>3. Stage Orchestrator + Implementation Loop</H3>
          <P>
            <Code>stage_orchestrator</Code> feeds one stage at a time to the{' '}
            <Code>implementation_loop</Code>, where the coding agent (Claude Code) writes and
            iteratively refines the code for that stage. After each stage,{' '}
            <Code>success_criteria_checker</Code> verifies the stage&apos;s empirical criteria
            against the actual run output, and <Code>stage_reflector</Code> — acting as an
            adaptive Principal Investigator — rewrites the remaining stages in light of what was
            just learned. Plans are not static; they evolve with the evidence.
          </P>

          <H3>4. Paper Writing Loop</H3>
          <P>
            Once every stage is complete, <Code>paper_writer_agent</Code> synthesizes the
            knowledge base, the experiment logs, and the metrics into a manuscript;{' '}
            <Code>paper_reviewer_agent</Code> reviews it inside{' '}
            <Code>paper_writing_loop</Code> for rigor and clarity before the LaTeX is compiled to
            PDF.
          </P>

          <H2 id="three-engines">Three Execution Engines: Orchestrated, Simple, Evolve</H2>
          <P>
            The CLI&apos;s <Code>--mode</Code> flag does not just change a setting — it routes
            execution through one of three structurally different engines.
          </P>
          <UL>
            <li>
              <strong>orchestrated</strong> — the full ADK agent graph described above. Best for
              open-ended research questions.
            </li>
            <li>
              <strong>simple</strong> — bypasses planning entirely and hands the prompt directly
              to the Claude Code agent. Faster and cheaper for narrowly-scoped coding tasks.
            </li>
            <li>
              <strong>evolve</strong> — replaces the implementation loop with{' '}
              <Code>EvolutionLoopAgent</Code>, an autonomous Darwinian optimization loop.
            </li>
          </UL>
          <H3>How the evolve loop actually works</H3>
          <P>
            Each generation, <Code>EvolutionLoopAgent</Code> samples a parent node from a FAISS
            vector database of previously-tried code variants, weighted toward
            higher-scoring nodes. It hands the parent&apos;s code and motivation to the coding
            agent with an explicit mutation task, runs the resulting script, and reads the new
            empirical score back out of <Code>results.json</Code>. An analyzer agent then
            reflects on whether the mutation helped or hurt, and the new node — code, score, and
            analysis — is committed back to the database. A{' '}
            <Code>BestSnapshotManager</Code> tracks the all-time best generation so the
            state-of-the-art result is never lost, even if a later mutation regresses.
          </P>

          <H2 id="structural-intelligence">Structural Code Intelligence</H2>
          <P>
            Reading entire files to understand a codebase wastes context window and invites
            mistakes. The <Code>review_agent</Code> instead queries a codebase knowledge graph
            built with <strong>Graphify</strong>, performing AST-level inspection of function
            signatures, call chains, and blast radius — reported to cut token usage by{' '}
            <strong>71.5x</strong> compared to reading raw source. This is how the system verifies
            mathematical correctness in a 10,000-line implementation without ever loading all
            10,000 lines into a prompt.
          </P>

          <H2 id="context-management">Context Window Management</H2>
          <P>
            Long-running research sessions can generate thousands of tool calls. Once a session
            crosses <strong>40 events</strong>, the framework triggers LLM-based event
            compression: the history is summarized and collapsed into a single context event,
            keeping multi-day sessions comfortably under a 1M-token window without losing the
            decisions that mattered.
          </P>

          <H2 id="research-vault">The Research Vault: Workspace Layout</H2>
          <P>Every run writes into a predictable, inspectable directory structure:</P>
          <UL>
            <li><Code>knowledge_base/</Code> — synthesized literature notes and architecture blueprints.</li>
            <li><Code>literature/</Code> — raw full-text sources pulled from ArXiv and Semantic Scholar.</li>
            <li><Code>workflow/</Code> — implementation code, training loops, and model modules.</li>
            <li><Code>results/</Code> — metric logs, checkpoints, and comparison plots.</li>
            <li><Code>manuscript/</Code> — the final, compiled LaTeX/PDF paper.</li>
          </UL>
          <P>
            This structure exists specifically to defeat <em>context amnesia</em>: an agent that
            gets compacted or restarted mid-session can re-orient itself by reading the vault
            instead of re-deriving everything from scratch.
          </P>

          <H2 id="event-model">Fully Observable: The Streaming Event Model</H2>
          <P>
            Internally, every agent action is normalized into one of eight typed events —{' '}
            <Code>message</Code>, <Code>function_call</Code>, <Code>function_response</Code>,{' '}
            <Code>file_created</Code>, <Code>usage</Code>, <Code>keepalive</Code>,{' '}
            <Code>error</Code>, and <Code>completed</Code> — and emitted as an async generator.
            That same stream can be consumed directly in Python, piped to a CLI, or forwarded
            over Server-Sent Events to a browser, which is what makes the entire research
            session replayable after the fact rather than a black box.
          </P>

          <H2 id="domains">Domain-Aware Prompting</H2>
          <P>
            The <Code>--domain</Code> flag injects domain-specific planning and review heuristics
            into every agent in the graph. Five domain packs ship today:{' '}
            <strong>AI/ML</strong>, <strong>finance</strong>, <strong>bioinformatics</strong>,{' '}
            <strong>algorithms</strong>, and <strong>physics</strong> — each tuning what counts as
            a rigorous baseline, an acceptable ablation, and a publishable result in that field.
          </P>

          <H2 id="toolbelt">The Toolbelt</H2>
          <P>Agents act on the world through a sandboxed set of tools, all scoped to the run&apos;s working directory:</P>
          <UL>
            <li><Code>research_ops</Code> — Semantic Scholar impact-filtering, multi-source paper search, and ArXiv full-text ingestion, with built-in rate limiting.</li>
            <li><Code>code_graph_ops</Code> — Graphify-backed codebase graph queries for AST-level structural review.</li>
            <li><Code>data_ops</Code> — DuckDB-powered SQL over Parquet files without loading datasets into memory.</li>
            <li><Code>latex_ops</Code> — compiles <Code>.tex</Code> manuscripts to PDF and surfaces syntax errors.</li>
            <li><Code>file_ops</Code> / <Code>web_ops</Code> — sandboxed file I/O and HTTP fetch tools, read-only and path-validated against the working directory.</li>
          </UL>

          <H2 id="getting-started">Getting Started</H2>
          <P>
            The entire pipeline above is one CLI invocation away, and the same engine is
            available as a plain async Python class for embedding into other systems.
          </P>
          <div className="rounded-xl overflow-hidden border border-white/10 shadow-lg bg-[#1E1E1E] my-6">
            <pre className="p-5 overflow-x-auto font-mono text-[12.5px] leading-relaxed text-white/85">
              <code>{`uv run ai-research-engineer "Investigate sparse mixture-of-experts \\
  routing in low-resource settings" --mode orchestrated`}</code>
            </pre>
          </div>
          <P>
            Full installation steps, CLI flags, the Python API, and the evolve-mode walkthrough
            live in the docs.
          </P>
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 font-body text-sm font-bold text-white bg-[#E05240] px-6 py-3 rounded-full hover:bg-[#D04130] transition-colors"
          >
            Read the Docs →
          </Link>

          <H2 id="faq">Frequently Asked Questions</H2>
          <div className="mt-2">
            <FAQ
              q="What is AI Research Engineer?"
              a="AI Research Engineer (codename Archimedes) is an open-source, multi-agent framework that automates the full lifecycle of machine learning research: hypothesis generation, literature review, experiment planning, code implementation, empirical validation, and final manuscript writing."
            />
            <FAQ
              q="What is the difference between orchestrated, simple, and evolve mode?"
              a="Orchestrated mode runs the full pipeline — ideation, planning, stage-by-stage implementation, reflection, and paper writing. Simple mode skips planning and runs the Claude Code agent directly for narrow coding tasks. Evolve mode runs a Darwinian optimization loop that samples a FAISS database of past code variants, mutates the best one, and keeps whatever improves the empirical score."
            />
            <FAQ
              q="Which AI models does AI Research Engineer use?"
              a="Orchestration and planning run on Gemini models via Google ADK and LiteLLM/OpenRouter, while code implementation is delegated to Claude (Claude Code CLI, default claude-sonnet-4-5) for surgical, AST-aware code edits."
            />
            <FAQ
              q="Can it replicate an existing paper instead of inventing something new?"
              a='Yes. The --research-mode flag toggles between "novelty" (inventing new architectures and validating them against the literature) and "replication" (strict reproduction of a target paper or benchmark).'
            />
            <FAQ
              q="Is the research output reproducible?"
              a="Every run produces a structured workspace (the Research Vault) containing the literature reviewed, the plan, the code, experiment logs, metrics, and the final manuscript, plus a full event-by-event session trace that can be replayed."
            />
            <FAQ
              q="Is AI Research Engineer open source?"
              a="Yes, it is released under the MIT license and available on GitHub at github.com/archimedes-run/ai-research-engineer."
            />
          </div>
        </motion.div>

        {/* Bottom CTA */}
        <div className="mt-16 pt-10 border-t border-[#3C2F2A]/10 flex flex-col md:flex-row items-center justify-between gap-6">
          <p className="font-display text-xl md:text-2xl text-[#3C2F2A]/50 italic">
            Read the source. It is all open.
          </p>
          <div className="flex items-center gap-3">
            <Link
              href="https://github.com/archimedes-run/ai-research-engineer"
              target="_blank"
              rel="noopener noreferrer"
              className="font-body text-xs uppercase tracking-[0.2em] text-white bg-[#3C2F2A] px-6 py-2.5 rounded-full hover:bg-[#2A201C] transition-all duration-300 font-bold"
            >
              View on GitHub
            </Link>
            <Link
              href="/blog"
              className="font-body text-xs uppercase tracking-[0.2em] text-[#E05240] border border-[#E05240]/30 px-6 py-2.5 rounded-full hover:bg-[#E05240] hover:text-white transition-all duration-300 font-bold"
            >
              Back to Blog
            </Link>
          </div>
        </div>
      </div>
    </article>
  )
}
