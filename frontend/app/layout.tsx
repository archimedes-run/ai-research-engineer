import type { Metadata } from 'next'
import { Cormorant_Garamond, Syne, Outfit, Fira_Code } from 'next/font/google'
import './globals.css'

const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
  style: ['normal', 'italic'],
  variable: '--font-cormorant',
  display: 'swap',
})

const syne = Syne({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-syne',
  display: 'swap',
})

const outfit = Outfit({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600'],
  variable: '--font-outfit',
  display: 'swap',
})

const firaCode = Fira_Code({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-fira-code',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Archimedes — Autonomous AI Research Lab',
  description:
    'The world\'s first autonomous AI research lab. From hypothesis to PyTorch implementation to academic paper. Watch Archimedes discover.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${cormorant.variable} ${syne.variable} ${outfit.variable} ${firaCode.variable}`}
    >
      <body className="bg-background text-ink antialiased">
        {children}
      </body>
    </html>
  )
}