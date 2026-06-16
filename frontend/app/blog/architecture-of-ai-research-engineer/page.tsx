import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import { Metadata } from 'next'
import ArticleClient from './ArticleClient'

const TITLE =
  'The Architecture of AI Research Engineer: How Archimedes Runs Autonomous AI Research'
const DESCRIPTION =
  'A technical deep dive into AI Research Engineer (Archimedes): the open-source multi-agent framework that turns a hypothesis, paper, dataset, or benchmark into a complete, reproducible research trace — ideation, planning, implementation, evolution, and a finished paper.'
const URL = 'https://archimedes.run/blog/architecture-of-ai-research-engineer'
const PUBLISHED = '2026-06-16'

export const metadata: Metadata = {
  title: `${TITLE} — Archimedes`,
  description: DESCRIPTION,
  keywords: [
    'AI Research Engineer',
    'Archimedes AI',
    'autonomous AI research agent',
    'multi-agent research framework',
    'Google ADK agent architecture',
    'Claude Code agent',
    'AI scientist agent',
    'automated machine learning research',
    'LLM agent orchestration',
    'AI research automation',
  ],
  alternates: { canonical: URL },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: URL,
    type: 'article',
    publishedTime: PUBLISHED,
    siteName: 'Archimedes',
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
  },
}

const articleJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'TechArticle',
  headline: TITLE,
  description: DESCRIPTION,
  datePublished: PUBLISHED,
  dateModified: PUBLISHED,
  url: URL,
  author: {
    '@type': 'Organization',
    name: 'Archimedes',
    url: 'https://archimedes.run',
  },
  publisher: {
    '@type': 'Organization',
    name: 'Archimedes',
    url: 'https://archimedes.run',
  },
  about: 'Autonomous AI research agent architecture',
  mainEntityOfPage: URL,
}

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [
    {
      '@type': 'Question',
      name: 'What is AI Research Engineer?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'AI Research Engineer (codename Archimedes) is an open-source, multi-agent framework that automates the full lifecycle of machine learning research: hypothesis generation, literature review, experiment planning, code implementation, empirical validation, and final manuscript writing.',
      },
    },
    {
      '@type': 'Question',
      name: 'What is the difference between orchestrated, simple, and evolve mode?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'Orchestrated mode runs the full pipeline — ideation, planning, stage-by-stage implementation, reflection, and paper writing. Simple mode skips planning and runs the Claude Code agent directly for narrow coding tasks. Evolve mode runs a Darwinian optimization loop that samples a FAISS database of past code variants, mutates the best one, and keeps whatever improves the empirical score.',
      },
    },
    {
      '@type': 'Question',
      name: 'Which AI models does AI Research Engineer use?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'Orchestration and planning run on Gemini models via Google ADK and LiteLLM/OpenRouter, while code implementation is delegated to Claude (Claude Code CLI, default claude-sonnet-4-5) for surgical, AST-aware code edits.',
      },
    },
    {
      '@type': 'Question',
      name: 'Can it replicate an existing paper instead of inventing something new?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'Yes. The --research-mode flag toggles between "novelty" (inventing new architectures and validating them against the literature) and "replication" (strict reproduction of a target paper or benchmark).',
      },
    },
    {
      '@type': 'Question',
      name: 'Is the research output reproducible?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'Every run produces a structured workspace (the Research Vault) containing the literature reviewed, the plan, the code, experiment logs, metrics, and the final manuscript, plus a full event-by-event session trace that can be replayed.',
      },
    },
    {
      '@type': 'Question',
      name: 'Is AI Research Engineer open source?',
      acceptedAnswer: {
        '@type': 'Answer',
        text:
          'Yes, it is released under the MIT license and available on GitHub at github.com/archimedes-run/ai-research-engineer.',
      },
    },
  ],
}

export default function ArchitectureArticlePage() {
  return (
    <main>
      <Navbar />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <ArticleClient />
      <Footer />
    </main>
  )
}
