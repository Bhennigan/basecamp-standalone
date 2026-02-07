import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { QueryProvider } from '@/components/providers/query-provider'
import { Sidebar } from '@/components/sidebar/sidebar'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Base Camp OS',
  description: 'Standalone Data Fusion Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <div className="flex h-screen">
            <Sidebar />
            <main className="flex-1 overflow-auto bg-gray-50">
              {children}
            </main>
          </div>
        </QueryProvider>
      </body>
    </html>
  )
}
