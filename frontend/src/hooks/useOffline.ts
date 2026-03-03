import { useState, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'

interface OfflineQueueItem {
  id: string
  type: 'conversation' | 'ticket' | 'settings'
  data: any
  timestamp: Date
  retryCount: number
}

export function useOffline() {
  const [offlineQueue, setOfflineQueue] = useState<OfflineQueueItem[]>([])
  const [isProcessingQueue, setIsProcessingQueue] = useState(false)
  const { isOnline, setOnlineStatus, addNotification } = useAppStore()

  // Load offline queue from localStorage on mount
  useEffect(() => {
    const savedQueue = localStorage.getItem('offline-queue')
    if (savedQueue) {
      try {
        const parsed = JSON.parse(savedQueue).map((item: any) => ({
          ...item,
          timestamp: new Date(item.timestamp)
        }))
        setOfflineQueue(parsed)
      } catch (error) {
        console.error('Failed to parse offline queue:', error)
        localStorage.removeItem('offline-queue')
      }
    }
  }, [])

  // Save offline queue to localStorage whenever it changes
  useEffect(() => {
    if (offlineQueue.length > 0) {
      localStorage.setItem('offline-queue', JSON.stringify(offlineQueue))
    } else {
      localStorage.removeItem('offline-queue')
    }
  }, [offlineQueue])

  // Monitor online/offline status
  useEffect(() => {
    const handleOnline = () => {
      setOnlineStatus(true)
      addNotification({
        type: 'success',
        message: 'Connection restored'
      })
      
      // Process offline queue when coming back online
      if (offlineQueue.length > 0) {
        processOfflineQueue()
      }
    }

    const handleOffline = () => {
      setOnlineStatus(false)
      addNotification({
        type: 'warning',
        message: 'You are now offline. Changes will be saved locally.'
      })
    }

    // Set initial state
    setOnlineStatus(navigator.onLine)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [setOnlineStatus, addNotification, offlineQueue.length])

  const addToOfflineQueue = (type: OfflineQueueItem['type'], data: any) => {
    const item: OfflineQueueItem = {
      id: crypto.randomUUID(),
      type,
      data,
      timestamp: new Date(),
      retryCount: 0
    }

    setOfflineQueue(prev => [...prev, item])
    
    addNotification({
      type: 'info',
      message: 'Changes saved offline. Will sync when connection is restored.'
    })

    return item.id
  }

  const removeFromOfflineQueue = (id: string) => {
    setOfflineQueue(prev => prev.filter(item => item.id !== id))
  }

  const processOfflineQueue = async () => {
    if (isProcessingQueue || !isOnline || offlineQueue.length === 0) {
      return
    }

    setIsProcessingQueue(true)
    
    addNotification({
      type: 'info',
      message: `Syncing ${offlineQueue.length} offline changes...`
    })

    let successCount = 0
    let failureCount = 0

    for (const item of offlineQueue) {
      try {
        // Simulate API call - replace with actual sync logic
        await syncOfflineItem(item)
        removeFromOfflineQueue(item.id)
        successCount++
      } catch (error) {
        console.error('Failed to sync offline item:', error)
        
        // Increment retry count
        setOfflineQueue(prev => 
          prev.map(queueItem => 
            queueItem.id === item.id 
              ? { ...queueItem, retryCount: queueItem.retryCount + 1 }
              : queueItem
          )
        )
        
        // Remove items that have failed too many times
        if (item.retryCount >= 3) {
          removeFromOfflineQueue(item.id)
          addNotification({
            type: 'error',
            message: `Failed to sync ${item.type} after multiple attempts`
          })
        }
        
        failureCount++
      }
    }

    setIsProcessingQueue(false)

    if (successCount > 0) {
      addNotification({
        type: 'success',
        message: `Successfully synced ${successCount} changes`
      })
    }

    if (failureCount > 0) {
      addNotification({
        type: 'warning',
        message: `${failureCount} changes failed to sync and will be retried`
      })
    }
  }

  const syncOfflineItem = async (item: OfflineQueueItem): Promise<void> => {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    switch (item.type) {
      case 'conversation':
        // Sync conversation data
        console.log('Syncing conversation:', item.data)
        break
      case 'ticket':
        // Sync ticket data
        console.log('Syncing ticket:', item.data)
        break
      case 'settings':
        // Sync settings data
        console.log('Syncing settings:', item.data)
        break
      default:
        throw new Error(`Unknown sync type: ${item.type}`)
    }
  }

  const clearOfflineQueue = () => {
    setOfflineQueue([])
    localStorage.removeItem('offline-queue')
    addNotification({
      type: 'info',
      message: 'Offline queue cleared'
    })
  }

  const getOfflineData = (type: OfflineQueueItem['type']) => {
    return offlineQueue.filter(item => item.type === type)
  }

  return {
    isOnline,
    offlineQueue,
    isProcessingQueue,
    addToOfflineQueue,
    removeFromOfflineQueue,
    processOfflineQueue,
    clearOfflineQueue,
    getOfflineData,
    hasOfflineChanges: offlineQueue.length > 0
  }
}