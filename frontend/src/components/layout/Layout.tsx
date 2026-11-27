import { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children?: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header />
      <main className="mx-auto max-w-screen-2xl px-4 py-6 sm:px-6 lg:px-8" id="main-content">
        {children || <Outlet />}
      </main>
      <footer className="border-t border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
        <div className="mx-auto max-w-screen-2xl px-4 py-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500 dark:text-gray-400">
            CurrencyTracker v0.1.0 - Monitor de Câmbio em Tempo Real
          </p>
        </div>
      </footer>
    </div>
  )
}

export function PageLayout({
  title,
  description,
  children,
  action,
}: {
  title: string
  description?: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
          {description && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>
          )}
        </div>
        {action && <div className="mt-4 sm:mt-0">{action}</div>}
      </div>
      {children}
    </div>
  )
}

export function Section({
  title,
  description,
  children,
  className,
}: {
  title?: string
  description?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('space-y-4', className)}>
      {(title || description) && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          {title && <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>}
          {description && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  )
}
