import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, X, Bell, Sun, Moon, ChevronDown, LogOut, User, Settings } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Visão Geral', href: '/', icon: 'Home' },
  { name: 'Comparação', href: '/comparison', icon: 'BarChart2' },
  { name: 'Previsões', href: '/predictions', icon: 'TrendingUp' },
  { name: 'Correlação', href: '/correlation', icon: 'GitBranch' },
  { name: 'Alertas', href: '/alerts', icon: 'Bell' },
]

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [darkMode, setDarkMode] = useState(false)
  const location = useLocation()

  const toggleDarkMode = () => {
    const newMode = !darkMode
    setDarkMode(newMode)
    document.documentElement.classList.toggle('dark', newMode)
    localStorage.setItem('darkMode', String(newMode))
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/80 backdrop-blur-lg dark:border-gray-700 dark:bg-gray-900/80">
      <div className="mx-auto flex h-16 max-w-screen-2xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2" aria-label="CurrencyTracker Home">
            <svg className="h-8 w-8 text-primary-600" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="2" />
              <path d="M16 8v16M8 16h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span className="font-bold text-xl text-gray-900 dark:text-white">CurrencyTracker</span>
          </Link>

          <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href ||
                (item.href !== '/' && location.pathname.startsWith(item.href))
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white'
                  )}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {item.name}
                </Link>
              )
            })}
          </nav>
        </div>

        
        <div className="flex items-center gap-2">
          
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleDarkMode}
            aria-label={darkMode ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
            className="md:hidden"
          >
            {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>

          
          <div className="relative">
            <Button variant="ghost" size="sm" aria-label="Notificações">
              <Bell className="h-5 w-5" />
              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-danger-500 text-[10px] font-bold text-white">
                3
              </span>
            </Button>
          </div>

          
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
              aria-expanded={userMenuOpen}
              aria-haspopup="true"
            >
              <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                <User className="h-5 w-5 text-primary-600" />
              </div>
              <span className="hidden sm:block">Usuário</span>
              <ChevronDown className="h-4 w-4" />
            </button>

            {userMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setUserMenuOpen(false)}
                  aria-hidden="true"
                />
                <div className="absolute right-0 mt-2 w-48 rounded-xl border border-gray-200 bg-white py-2 shadow-lg dark:border-gray-700 dark:bg-gray-800 animate-slide-down">
                  <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">Usuário Demo</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">demo@currencytracker.com</p>
                  </div>
                  <Link
                    to="/settings"
                    className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <Settings className="h-4 w-4" />
                    Configurações
                  </Link>
                  <button
                    className="flex w-full items-center gap-2 px-4 py-2 text-sm text-danger-600 hover:bg-gray-100 dark:hover:bg-gray-700"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <LogOut className="h-4 w-4" />
                    Sair
                  </button>
                </div>
              </>
            )}
          </div>

          
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={mobileMenuOpen}
            className="md:hidden"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </Button>
        </div>
      </div>

      
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-gray-200 bg-white py-4 dark:border-gray-700 dark:bg-gray-900 animate-slide-down">
          <nav className="mx-auto max-w-screen-2xl px-4" aria-label="Mobile navigation">
            <div className="flex items-center justify-between mb-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleDarkMode}
                aria-label={darkMode ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
              >
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                <span>{darkMode ? 'Modo Claro' : 'Modo Escuro'}</span>
              </Button>
            </div>
            <ul className="space-y-1" role="list">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href ||
                  (item.href !== '/' && location.pathname.startsWith(item.href))
                return (
                  <li key={item.name}>
                    <Link
                      to={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary-50 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400'
                          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white'
                      )}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      {item.name}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </div>
      )}
    </header>
  )
}
