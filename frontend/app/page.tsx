import Navbar from '@/components/Navbar'
import Hero from '@/components/Hero'
import Direction from '@/components/Direction'
import KnowledgeGraphSection from '@/components/KnowledgeGraphSection'
import Pipeline from '@/components/Pipeline'
import Footer from '@/components/Footer'
import ScrollProgress from '@/components/ScrollProgress'

export default function Home() {
  return (
    <main>
      <ScrollProgress />
      <Navbar />
      <Hero />
      <Direction />
      <KnowledgeGraphSection />
      <Pipeline />
      <Footer />
    </main>
  )
}
