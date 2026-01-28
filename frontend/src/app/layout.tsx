import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { PasswordGate } from '@/components/auth'
import { ToastProvider } from '@/components/ui'
import { PipelineProvider } from '@/contexts/PipelineContext'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'C1 Intelligence Hub',
  description: 'Real-time supply chain intelligence for the composites industry',
  icons: {
    icon: '/favicon.png',
    apple: '/favicon.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-slate-100 text-slate-900 min-h-screen antialiased`}>
        <ToastProvider>
          <PasswordGate>
            <PipelineProvider>
              {children}
            </PipelineProvider>
          </PasswordGate>
        </ToastProvider>
      </body>
    </html>
  )
}
