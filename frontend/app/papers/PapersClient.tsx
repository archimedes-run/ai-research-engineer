'use client'

import { motion } from 'framer-motion'
import { FileText, ExternalLink, Download, CheckCircle, Clock, Send, BookOpen } from 'lucide-react'
import Link from 'next/link'

type PaperStatus = 'Published' | 'Submitted' | 'Writing' | 'Running'

type Paper = {
  id: string
  sessionId: string
  title: string
  authors: string
  venue: string
  year: number
  status: PaperStatus
  abstract: string
  tags: string[]
  pdfUrl?: string
  arxivUrl?: string
}

const papers: Paper[] = [
  {
    id: 'ARC-2026-051',
    sessionId: 'arc2026051',
    title: 'Wavelet-KAN: Spline-Wavelet Hybrid Networks for Time-Series Forecasting with Zero Data Leakage',
    authors: 'Archimedes Research Lab',
    venue: 'ICML 2026',
    year: 2026,
    status: 'Running',
    abstract: 'We propose Wavelet-KAN, a hybrid architecture combining Kolmogorov-Arnold Networks with discrete wavelet transforms for multivariate time-series forecasting. The model achieves perfect IDWT reconstruction — a criterion no prior work has explicitly targeted — while maintaining zero data leakage across all validation protocols.',
    tags: ['Time-Series', 'KAN', 'Wavelet', 'PyTorch', 'CUDA'],
  },
  {
    id: 'ARC-2026-050',
    sessionId: 'arc2026050',
    title: 'Sparse Mixture-of-Experts with Dynamic Routing in Low-Resource Natural Language Settings',
    authors: 'Archimedes Research Lab',
    venue: 'NeurIPS 2026',
    year: 2026,
    status: 'Writing',
    abstract: 'Dynamic routing in sparse MoE architectures typically degrades under low-resource conditions due to expert collapse. We introduce an adaptive load-balancing mechanism that maintains expert utilization above 85% even with fewer than 1,000 training examples per domain.',
    tags: ['MoE', 'Low-Resource', 'NLP', 'Routing'],
  },
  {
    id: 'ARC-2026-049',
    sessionId: 'arc2026049',
    title: 'Contrastive Pretraining for Time-Series Anomaly Detection in Biological Measurement Systems',
    authors: 'Archimedes Research Lab',
    venue: 'ACL 2026',
    year: 2026,
    status: 'Submitted',
    abstract: 'We adapt contrastive self-supervised pretraining to the biological time-series domain, where labeled anomaly examples are scarce and distributional shifts are frequent. Our method achieves state-of-the-art performance on five benchmark datasets without any labeled anomaly data during pretraining.',
    tags: ['Anomaly Detection', 'Contrastive Learning', 'Biology', 'Self-Supervised'],
    pdfUrl: '#',
    arxivUrl: '#',
  },
  {
    id: 'ARC-2026-048',
    sessionId: 'arc2026048',
    title: 'Emergent Tool Use in Reinforcement Learning Agents Without Explicit Reward Shaping',
    authors: 'Archimedes Research Lab',
    venue: 'ICLR 2026',
    year: 2026,
    status: 'Published',
    abstract: 'We demonstrate that tool use emerges spontaneously in RL agents trained on sparse reward signals when given access to a structured action vocabulary. No explicit reward shaping for tool interactions is required — the agent discovers compositional tool use as an instrumental convergent strategy.',
    tags: ['Reinforcement Learning', 'Tool Use', 'Emergence', 'Sparse Reward'],
    pdfUrl: '#',
    arxivUrl: '#',
  },
]

const statusConfig: Record<PaperStatus, { label: string; color: string; dotColor: string; icon: React.ReactNode }> = {
  Published: {
    label: 'Published',
    color: 'text-[#E05240] bg-[#E05240]/8 border-[#E05240]/20',
    dotColor: 'bg-[#E05240]',
    icon: <CheckCircle className="w-3 h-3" />,
  },
  Submitted: {
    label: 'Under Review',
    color: 'text-blue-600 bg-blue-50 border-blue-200',
    dotColor: 'bg-blue-400',
    icon: <Send className="w-3 h-3" />,
  },
  Writing: {
    label: 'Writing',
    color: 'text-amber-600 bg-amber-50 border-amber-200',
    dotColor: 'bg-amber-400',
    icon: <BookOpen className="w-3 h-3" />,
  },
  Running: {
    label: 'In Progress',
    color: 'text-orange-600 bg-orange-50 border-orange-200',
    dotColor: 'bg-orange-500',
    icon: <Clock className="w-3 h-3" />,
  },
}

export default function PapersClient() {
  const published = papers.filter(p => p.status === 'Published' || p.status === 'Submitted')
  const inProgress = papers.filter(p => p.status === 'Writing' || p.status === 'Running')

  return (
    <div className="min-h-screen bg-[#FCF1EB] paper-grain">

      {/* Page Header */}
      <div className="pt-40 pb-16 px-6 max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mb-4"
        >
          <span className="font-mono text-[10px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
            Research Output
          </span>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col md:flex-row md:items-end justify-between gap-8"
        >
          <h1 className="font-display text-6xl md:text-8xl text-[#3C2F2A] italic leading-[1.0]">
            Papers.
          </h1>
          <p className="font-body text-base text-[#3C2F2A]/60 max-w-sm leading-relaxed pb-2">
            Publication-ready manuscripts generated by the Synthesis Agent. Each paper links to its full execution context.
          </p>
        </motion.div>
      </div>

      <div className="max-w-7xl mx-auto px-6">
        <div className="h-px bg-[#3C2F2A]/10" />
      </div>

      {/* Stats bar */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="max-w-7xl mx-auto px-6 py-8"
      >
        <div className="flex gap-10 md:gap-20">
          <div>
            <div className="font-display text-3xl text-[#3C2F2A]">
              {papers.filter(p => p.status === 'Published').length}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#3C2F2A]/40 mt-0.5">Published</div>
          </div>
          <div>
            <div className="font-display text-3xl text-[#3C2F2A]">
              {papers.filter(p => p.status === 'Submitted').length}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#3C2F2A]/40 mt-0.5">Under Review</div>
          </div>
          <div>
            <div className="font-display text-3xl text-[#3C2F2A]">
              {papers.filter(p => p.status === 'Writing' || p.status === 'Running').length}
            </div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[#3C2F2A]/40 mt-0.5">In Progress</div>
          </div>
        </div>
      </motion.div>

      {/* Papers List */}
      <div className="max-w-7xl mx-auto px-6 pb-24">

        {/* Published & Submitted */}
        <div className="mb-20">
          <div className="flex items-center gap-4 mb-8">
            <h2 className="font-mono text-[10px] tracking-[0.3em] uppercase text-[#3C2F2A]/40 font-bold">
              Completed
            </h2>
            <div className="flex-1 h-px bg-[#3C2F2A]/8" />
          </div>

          <div className="space-y-0">
            {published.map((paper, i) => (
              <PaperRow key={paper.id} paper={paper} index={i} />
            ))}
          </div>
        </div>

        {/* In Progress */}
        <div>
          <div className="flex items-center gap-4 mb-8">
            <h2 className="font-mono text-[10px] tracking-[0.3em] uppercase text-[#3C2F2A]/40 font-bold">
              In Progress
            </h2>
            <div className="flex-1 h-px bg-[#3C2F2A]/8" />
          </div>

          <div className="space-y-0">
            {inProgress.map((paper, i) => (
              <PaperRow key={paper.id} paper={paper} index={i + published.length} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function PaperRow({ paper, index }: { paper: Paper; index: number }) {
  const cfg = statusConfig[paper.status]

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.05 + index * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="group border-b border-[#3C2F2A]/8 py-8 hover:bg-white/30 transition-colors duration-300 px-4 -mx-4 rounded-xl"
    >
      {/* Top row: id, venue, status */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <span className="font-mono text-[9px] tracking-widest uppercase text-[#3C2F2A]/30">
          {paper.id}
        </span>
        <span className="w-1 h-1 rounded-full bg-[#3C2F2A]/20" />
        <span className="font-mono text-[9px] tracking-widest uppercase text-[#3C2F2A]/30">
          {paper.venue} · {paper.year}
        </span>
        <div className={`ml-auto flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[9px] font-mono uppercase tracking-wider font-bold ${cfg.color}`}>
          {cfg.icon}
          {cfg.label}
        </div>
      </div>

      {/* Title */}
      <h3 className="font-display text-xl md:text-2xl text-[#3C2F2A] italic leading-snug mb-3 group-hover:text-[#E05240] transition-colors duration-300 max-w-3xl">
        {paper.title}
      </h3>

      {/* Abstract */}
      <p className="font-body text-sm text-[#3C2F2A]/55 leading-relaxed max-w-3xl line-clamp-2 mb-4">
        {paper.abstract}
      </p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-5">
        {paper.tags.map((tag) => (
          <span
            key={tag}
            className="font-mono text-[8px] tracking-widest uppercase text-[#3C2F2A]/35 border border-[#3C2F2A]/10 px-2 py-0.5 rounded"
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Action row */}
      <div className="flex items-center gap-4 flex-wrap">
        {paper.pdfUrl ? (
          <a
            href={paper.pdfUrl}
            className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest font-bold text-white bg-[#3C2F2A] hover:bg-[#E05240] transition-colors duration-300 px-4 py-2 rounded-lg"
          >
            <Download className="w-3.5 h-3.5" />
            PDF
          </a>
        ) : (
          <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest font-bold text-[#3C2F2A]/30 border border-[#3C2F2A]/10 px-4 py-2 rounded-lg">
            <FileText className="w-3.5 h-3.5" />
            PDF Pending
          </span>
        )}

        <Link
          href={`/sessions/${paper.sessionId}`}
          className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest font-bold text-[#E05240] border border-[#E05240]/25 hover:bg-[#E05240] hover:text-white transition-all duration-300 px-4 py-2 rounded-lg"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          View Session Context
        </Link>

        {paper.arxivUrl && (
          <a
            href={paper.arxivUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[10px] uppercase tracking-widest text-[#3C2F2A]/40 hover:text-[#3C2F2A] transition-colors duration-200"
          >
            arXiv →
          </a>
        )}
      </div>
    </motion.div>
  )
}
