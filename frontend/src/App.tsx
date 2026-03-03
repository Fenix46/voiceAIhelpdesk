import { BrowserRouter as Router } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { queryClient } from '@/lib/queryClient'
import { AppRouter } from '@/router/AppRouter'
import { ThemeProvider } from '@/providers/ThemeProvider'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

function AppContent() {
  useKeyboardShortcuts()
  
  return (
    <Router>
      <AppRouter />
    </Router>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AppContent />
        </ThemeProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
