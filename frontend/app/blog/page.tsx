import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import { Metadata } from 'next'
import BlogClient from './BlogClient'

export const metadata: Metadata = {
  title: 'Blog — Archimedes Research Lab',
  description: 'Insights from the frontier of autonomous AI research.',
}

export default function BlogPage() {
  return (
    <main>
      <Navbar />
      <BlogClient />
      <Footer />
    </main>
  )
}
