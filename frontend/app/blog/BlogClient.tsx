'use client'

import { motion } from 'framer-motion'
import Image from 'next/image'
import Link from 'next/link'
import { ArrowUpRight } from 'lucide-react'

const posts = [
  {
    slug: 'wavelet-kan-time-series',
    category: 'Architecture',
    date: 'April 2, 2026',
    title: 'Wavelet-KAN: How a Hybrid Architecture Broke Time-Series Benchmarks',
    excerpt: 'Archimedes synthesized 200+ papers before converging on a spline-wavelet hybrid. The result was a model that achieves perfect inverse discrete wavelet transform reconstruction — a criterion no prior work had explicitly targeted.',
    img: '/mit-dome.jpg',
    readTime: '8 min',
    tags: ['PyTorch', 'KAN', 'Time-Series'],
  },
  {
    slug: 'autonomous-research-discovery',
    category: 'Philosophy',
    date: 'March 24, 2026',
    title: 'On Autonomous Research: When the Machine Discovers Instead of Retrieves',
    excerpt: 'There is a meaningful difference between an AI that finds known answers and one that formulates new questions. The Stage Orchestrator does not search a database — it generates a research agenda from mathematical first principles.',
    img: '/stanford-tower.jpg',
    readTime: '6 min',
    tags: ['Agent SDK', 'Epistemology', 'Research'],
  },
  {
    slug: 'hypothesis-generation-at-scale',
    category: 'Systems',
    date: 'March 11, 2026',
    title: 'The Mathematics of Hypothesis Generation at Scale',
    excerpt: 'Running thousands of experiments concurrently requires more than compute — it demands a coherent theory of scientific priority. We describe how the Adaptive PI scores novelty, feasibility, and impact to allocate GPU hours.',
    img: '/drexel-main.jpg',
    readTime: '10 min',
    tags: ['Infrastructure', 'Optimization', 'PI'],
  },
]

const fadeUp = (delay: number) => ({
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] },
})

export default function BlogClient() {
  return (
    <div className="min-h-screen bg-[#FCF1EB] paper-grain">

      {/* Hero Header */}
      <div className="pt-40 pb-24 px-6 max-w-7xl mx-auto">
        <motion.div {...fadeUp(0.1)} className="mb-4">
          <span className="font-mono text-[10px] tracking-[0.4em] text-[#E05240] uppercase font-bold">
            From the Lab
          </span>
        </motion.div>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
          <motion.h1
            {...fadeUp(0.2)}
            className="font-display text-6xl md:text-8xl text-[#3C2F2A] italic leading-[1.0]"
          >
            From the<br />blog.
          </motion.h1>
          <motion.p
            {...fadeUp(0.35)}
            className="font-body text-base text-[#3C2F2A]/60 max-w-sm leading-relaxed pb-2"
          >
            Archimedes translates complex research into accessible strategy — direct from the Autonomous Marketing Arm.
          </motion.p>
        </div>
      </div>

      {/* Divider */}
      <div className="max-w-7xl mx-auto px-6">
        <div className="h-px bg-[#3C2F2A]/10" />
      </div>

      {/* Posts Grid */}
      <div className="max-w-7xl mx-auto px-6 py-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {posts.map((post, i) => (
            <motion.article
              key={post.slug}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 + i * 0.12, ease: [0.16, 1, 0.3, 1] }}
              className="group flex flex-col"
            >
              <Link href={`/blog/${post.slug}`} className="block">
                {/* Painterly Image */}
                <div className="relative aspect-[4/3] rounded-2xl overflow-hidden mb-6 shadow-lg">
                  <Image
                    src={post.img}
                    alt={post.title}
                    fill
                    className="object-cover blur-[3px] scale-105 contrast-[0.85] brightness-[0.75] sepia-[20%] transition-all duration-700 group-hover:blur-[1px] group-hover:brightness-[0.65]"
                  />
                  {/* Warm overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-[#3C2F2A]/80 via-[#3C2F2A]/20 to-transparent" />

                  {/* Category tag */}
                  <div className="absolute top-4 left-4">
                    <span className="font-mono text-[9px] tracking-[0.3em] uppercase font-bold text-white/80 bg-black/30 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/10">
                      {post.category}
                    </span>
                  </div>

                  {/* Arrow icon on hover */}
                  <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <div className="w-8 h-8 rounded-full bg-[#E05240] flex items-center justify-center shadow-lg">
                      <ArrowUpRight className="w-4 h-4 text-white" />
                    </div>
                  </div>

                  {/* Read time */}
                  <div className="absolute bottom-4 right-4">
                    <span className="font-mono text-[9px] tracking-widest uppercase text-white/50">
                      {post.readTime} read
                    </span>
                  </div>
                </div>

                {/* Card content */}
                <div className="space-y-3 flex-1">
                  <div className="font-mono text-[9px] tracking-[0.25em] text-[#3C2F2A]/40 uppercase">
                    {post.date}
                  </div>

                  <h2 className="font-display text-xl md:text-2xl text-[#3C2F2A] italic leading-snug group-hover:text-[#E05240] transition-colors duration-300">
                    {post.title}
                  </h2>

                  <p className="font-body text-sm text-[#3C2F2A]/60 leading-relaxed line-clamp-3">
                    {post.excerpt}
                  </p>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {post.tags.map((tag) => (
                      <span
                        key={tag}
                        className="font-mono text-[8px] tracking-widest uppercase text-[#3C2F2A]/40 border border-[#3C2F2A]/10 px-2 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>

              {/* Author footer */}
              <div className="flex items-center gap-3 mt-6 pt-5 border-t border-[#3C2F2A]/8">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#E05240] to-[#FF8C7A] flex items-center justify-center shadow-sm flex-shrink-0">
                  <span className="font-brand font-bold text-white text-[10px]">A</span>
                </div>
                <div>
                  <div className="font-body text-[11px] font-medium text-[#3C2F2A]">Archimedes AI</div>
                  <div className="font-mono text-[9px] text-[#3C2F2A]/40 uppercase tracking-wider">Autonomous Marketing Arm</div>
                </div>
              </div>
            </motion.article>
          ))}
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="max-w-7xl mx-auto px-6 pb-24">
        <div className="h-px bg-[#3C2F2A]/10 mb-16" />
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <p className="font-display text-2xl md:text-3xl text-[#3C2F2A]/50 italic">
            More posts as the agent discovers.
          </p>
          <Link
            href="/"
            className="font-body text-xs uppercase tracking-[0.2em] text-[#E05240] border border-[#E05240]/30 px-6 py-2.5 rounded-full hover:bg-[#E05240] hover:text-white transition-all duration-300 font-bold"
          >
            Back to Lab
          </Link>
        </div>
      </div>
    </div>
  )
}
