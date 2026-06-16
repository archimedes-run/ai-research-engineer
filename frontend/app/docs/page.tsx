import Navbar from '@/components/Navbar'
import Footer from '@/components/Footer'
import { Metadata } from 'next'
import DocsClient from './DocsClient'

export const metadata: Metadata = {
  title: 'Docs — AI Research Engineer',
  description:
    'How to install and run AI Research Engineer (Archimedes): the open-source autonomous research framework that turns a hypothesis, paper, dataset, or benchmark into a complete, reproducible research trace.',
}

export default function DocsPage() {
  return (
    <main>
      <Navbar />
      <DocsClient />
      <Footer />
    </main>
  )
}
