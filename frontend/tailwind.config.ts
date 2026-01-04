import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // C1 Brand Colors
        c1: {
          navy: '#0f4c8b',
          'navy-light': '#4a7ab5',
          purple: '#7d4199',
          'purple-light': '#a87bb8',
        },
        // Dark mode base
        background: {
          primary: '#0f172a',
          secondary: '#1e293b',
          tertiary: '#334155',
          card: '#1e293b',
        },
        // Text colors
        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#64748b',
        },
        // Segment colors
        segment: {
          raw: '#3b82f6',
          intermediate: '#7d4199',
          distributor: '#0f4c8b',
          processor: '#f97316',
          oem: '#10b981',
        },
      },
      boxShadow: {
        'glow-purple': '0 0 30px rgba(125, 65, 153, 0.3)',
      },
    },
  },
  plugins: [],
}

export default config
