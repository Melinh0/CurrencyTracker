import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info' | 'outline'
  size?: 'sm' | 'md'
  dot?: boolean
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', dot, children, ...props }, ref) => {
    const variants = {
      default: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
      success: 'bg-success-50 text-success-600 dark:bg-success-500/20 dark:text-success-400',
      danger: 'bg-danger-50 text-danger-600 dark:bg-danger-500/20 dark:text-danger-400',
      warning: 'bg-warning-50 text-warning-600 dark:bg-warning-500/20 dark:text-warning-400',
      info: 'bg-primary-50 text-primary-600 dark:bg-primary-500/20 dark:text-primary-400',
      outline: 'bg-transparent border border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-0.5 text-xs',
    }

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full font-medium',
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {dot && (
          <span
            className={cn(
              'relative flex h-1.5 w-1.5 rounded-full',
              variant === 'success' && 'bg-success-500',
              variant === 'danger' && 'bg-danger-500',
              variant === 'warning' && 'bg-warning-500',
              variant === 'info' && 'bg-primary-500',
              variant === 'default' && 'bg-gray-500',
              variant === 'outline' && 'bg-gray-500'
            )}
          />
        )}
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'
