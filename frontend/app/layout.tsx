import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import ThemeRegistry from './ThemeRegistry'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Job Offers Scraper',
  description: 'Scraper ofert pracy z różnych portali',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pl" style={{ height: '100%' }}>
      <body className={inter.className} style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <ThemeRegistry>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            {children}
          </div>
        </ThemeRegistry>
      </body>
    </html>
  )
}
