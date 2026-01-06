import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { PasswordGate } from '@/components/auth'
import { ToastProvider } from '@/components/ui'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'C1 Intelligence Hub',
  description: 'Real-time supply chain intelligence for the composites industry',
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
            {children}
          </PasswordGate>
        </ToastProvider>
      </body>
    </html>
  )
}
