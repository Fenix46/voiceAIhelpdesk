import { useState, useRef, useCallback } from 'react'

interface LoadingState {
  isLoading: boolean
  error: Error | null
  progress?: number
}

type LoadingStates = Record<string, LoadingState>

export function useLoading() {
  const [loadingStates, setLoadingStates] = useState<LoadingStates>({})
  const timeoutRefs = useRef<Record<string, NodeJS.Timeout>>({})

  const setLoading = useCallback((key: string, isLoading: boolean, error?: Error | null, progress?: number) => {
    setLoadingStates(prev => ({
      ...prev,
      [key]: {
        isLoading,
        error: error || null,
        progress
      }
    }))

    // Clear any existing timeout for this key
    if (timeoutRefs.current[key]) {
      clearTimeout(timeoutRefs.current[key])
      delete timeoutRefs.current[key]
    }

    // Set a safety timeout to prevent stuck loading states
    if (isLoading) {
      timeoutRefs.current[key] = setTimeout(() => {
        setLoadingStates(prev => ({
          ...prev,
          [key]: {
            isLoading: false,
            error: new Error('Operation timed out'),
            progress: undefined
          }
        }))
        delete timeoutRefs.current[key]
      }, 30000) // 30 second timeout
    }
  }, [])

  const getLoadingState = useCallback((key: string): LoadingState => {
    return loadingStates[key] || { isLoading: false, error: null }
  }, [loadingStates])

  const isAnyLoading = useCallback((): boolean => {
    return Object.values(loadingStates).some(state => state.isLoading)
  }, [loadingStates])

  const clearLoading = useCallback((key: string) => {
    setLoadingStates(prev => {
      const newStates = { ...prev }
      delete newStates[key]
      return newStates
    })

    if (timeoutRefs.current[key]) {
      clearTimeout(timeoutRefs.current[key])
      delete timeoutRefs.current[key]
    }
  }, [])

  const clearAllLoading = useCallback(() => {
    setLoadingStates({})
    
    // Clear all timeouts
    Object.values(timeoutRefs.current).forEach(timeout => clearTimeout(timeout))
    timeoutRefs.current = {}
  }, [])

  // Wrapper function for async operations
  const withLoading = useCallback(async <T>(
    key: string,
    operation: () => Promise<T>,
    onProgress?: (progress: number) => void
  ): Promise<T> => {
    try {
      setLoading(key, true)
      
      if (onProgress) {
        const progressInterval = setInterval(() => {
          // Simulate progress for operations without real progress tracking
          setLoadingStates(prev => {
            const current = prev[key]?.progress || 0
            const newProgress = Math.min(current + Math.random() * 10, 90)
            onProgress(newProgress)
            
            return {
              ...prev,
              [key]: {
                ...prev[key],
                progress: newProgress
              }
            }
          })
        }, 500)

        const result = await operation()
        
        clearInterval(progressInterval)
        setLoading(key, false, null, 100)
        
        // Clear the completed state after a short delay
        setTimeout(() => clearLoading(key), 1000)
        
        return result
      } else {
        const result = await operation()
        setLoading(key, false)
        return result
      }
    } catch (error) {
      setLoading(key, false, error as Error)
      throw error
    }
  }, [setLoading, clearLoading])

  // Cleanup timeouts on unmount
  const cleanup = useCallback(() => {
    Object.values(timeoutRefs.current).forEach(timeout => clearTimeout(timeout))
    timeoutRefs.current = {}
  }, [])

  return {
    loadingStates,
    setLoading,
    getLoadingState,
    isAnyLoading,
    clearLoading,
    clearAllLoading,
    withLoading,
    cleanup
  }
}