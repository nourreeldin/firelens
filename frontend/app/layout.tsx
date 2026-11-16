import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import './globals.css'
import { Providers } from './providers'
import { extensionHostProps } from '@/lib/extension-compat'

export const metadata: Metadata = {
  title: 'FireLens | Fire Activity Dashboard',
  description: 'Satellite fire observations, harmonized activity, historical analytics, and method validation for NASA Space Apps Cairo 2026.',
  generator: 'FireLens',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png?v=firelens-1',
        sizes: '32x32',
        type: 'image/png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png?v=firelens-1',
        sizes: '32x32',
        type: 'image/png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg?v=firelens-1',
        sizes: 'any',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png?v=firelens-1',
  },
}

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: 'white' },
    { media: '(prefers-color-scheme: dark)', color: 'black' },
  ],
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        <div {...extensionHostProps} />
        {/** @v0-skip */}
        <Providers>{children}</Providers>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
