import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Light theme foundation
        background: '#FAFAFA',
        brand: {
          DEFAULT: '#E05240', // The sunset orange
          light: '#FF6A58',
          dim: '#9E3428',
        },
        ink: {
          DEFAULT: '#1E293B', // High contrast dark slate for text
          muted: '#475569',   // Softer text for subtitles
          dim: '#64748B',
          faint: '#94A3B8',
        },
        surface: {
          DEFAULT: '#FFFFFF', // Pure white for cards/terminal background
          alt: '#F8FAFC',     // Slight offset for hover states
        },
        edge: {
          DEFAULT: '#E2E8F0', // Clean light borders
          bright: '#CBD5E1',
        },
      },
      fontFamily: {
        display: ['var(--font-space-grotesk)', 'system-ui', 'sans-serif'],
        body: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-fira-code)', 'monospace'],
      },
    },
  },
  plugins: [],
}

export default config