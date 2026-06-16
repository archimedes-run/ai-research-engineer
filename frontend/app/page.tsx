import Navbar from '@/components/Navbar'
import Hero from '@/components/Hero'
import Pipeline from '@/components/Pipeline'
import ActiveSessions from '@/components/ActiveSessions'
import Footer from '@/components/Footer'
import ResearchSubmissionForm from '@/components/ResearchSubmissionForm'

export default function Home() {
  return (
    <main>
      <Navbar />
      <Hero />
      <ResearchSubmissionForm />
      <Pipeline />
      <ActiveSessions />
      <Footer />
    </main>
  )
}
