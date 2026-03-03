import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/providers/ThemeProvider'
import { useAppStore } from '@/store/appStore'
import { 
  Home, 
  MessageCircle, 
  BarChart3, 
  Ticket, 
  Settings,
  Sun,
  Moon,
  Wifi,
  WifiOff
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function Navigation() {
  const location = useLocation()
  const { theme, setTheme } = useTheme()
  const { isOnline } = useAppStore()

  const navItems = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/conversation', label: 'Conversation', icon: MessageCircle },
    { path: '/dashboard', label: 'Dashboard', icon: BarChart3 },
    { path: '/tickets', label: 'Tickets', icon: Ticket },
    { path: '/settings', label: 'Settings', icon: Settings },
  ]

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light')
  }

  return (
    <nav 
      id="navigation" 
      className="border-b bg-card"
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-4">
            <Link 
              to="/" 
              className="font-bold text-xl text-primary"
              aria-label="VoiceHelpDesk home page"
            >
              VoiceHelpDesk
            </Link>
            <div className="hidden md:flex space-x-1" role="menubar">
              {navItems.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  role="menuitem"
                  aria-current={location.pathname === path ? "page" : undefined}
                  className={cn(
                    "px-3 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-ring",
                    location.pathname === path
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <div className="flex items-center space-x-2">
                    <Icon size={16} aria-hidden="true" />
                    <span>{label}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <div 
              className="flex items-center space-x-1 text-sm text-muted-foreground"
              role="status"
              aria-live="polite"
            >
              {isOnline ? (
                <Wifi size={16} className="text-green-500" aria-hidden="true" />
              ) : (
                <WifiOff size={16} className="text-red-500" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">
                {isOnline ? 'Online' : 'Offline'}
              </span>
              <span className="sr-only">
                Connection status: {isOnline ? 'Connected to internet' : 'Disconnected from internet'}
              </span>
            </div>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              aria-pressed={theme === 'dark'}
            >
              {theme === 'dark' ? (
                <Sun size={16} aria-hidden="true" />
              ) : (
                <Moon size={16} aria-hidden="true" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile menu - simplified for now */}
      <div className="md:hidden border-t bg-card/95 backdrop-blur">
        <div className="container mx-auto px-4 py-2">
          <div className="flex flex-wrap gap-2">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={cn(
                  "flex items-center space-x-1 px-2 py-1 rounded text-xs font-medium transition-colors",
                  location.pathname === path
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-accent hover:text-accent-foreground"
                )}
                aria-current={location.pathname === path ? "page" : undefined}
              >
                <Icon size={14} aria-hidden="true" />
                <span>{label}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}