import { Navigation } from '@/components/Navigation'
import { NotificationCenter } from '@/components/NotificationCenter'
import { OfflineBanner } from '@/components/OfflineBanner'
import { LoadingOverlay } from '@/components/LoadingOverlay'
import { useAccessibility } from '@/hooks/useAccessibility'
import { useOffline } from '@/hooks/useOffline'
import { useLoading } from '@/hooks/useLoading'
import { useEffect } from 'react'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const { skipToContent, skipToNavigation } = useAccessibility()
  const { hasOfflineChanges } = useOffline()
  const { cleanup } = useLoading()

  // Cleanup loading states on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  return (
    <div className="min-h-screen bg-background">
      {/* Skip Links */}
      <a
        href="#main-content"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault()
          skipToContent()
        }}
      >
        Skip to main content
      </a>
      <a
        href="#navigation"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault()
          skipToNavigation()
        }}
      >
        Skip to navigation
      </a>

      {/* Screen reader announcements */}
      <div aria-live="polite" aria-atomic="true" className="sr-only" id="status-announcements" />
      <div aria-live="assertive" aria-atomic="true" className="sr-only" id="alert-announcements" />

      <Navigation />
      
      {/* Offline/Online Status Banner */}
      <OfflineBanner />
      
      <main 
        id="main-content" 
        className="container mx-auto px-4 py-6"
        tabIndex={-1}
        role="main"
        aria-label="Main content"
      >
        {children}
      </main>
      
      <NotificationCenter />
      
      {/* Global Loading Overlay */}
      <LoadingOverlay />
    </div>
  )
}