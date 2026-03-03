import { useEffect } from 'react'
import { useAppStore } from '@/store/appStore'
import { X, CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

export function NotificationCenter() {
  const { notifications, removeNotification } = useAppStore()

  useEffect(() => {
    const timer = setInterval(() => {
      notifications.forEach((notification) => {
        const age = Date.now() - notification.timestamp.getTime()
        if (age > 5000) { // Auto-remove after 5 seconds
          removeNotification(notification.id)
        }
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [notifications, removeNotification])

  if (notifications.length === 0) return null

  const getIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle size={16} className="text-green-500" />
      case 'error': return <XCircle size={16} className="text-red-500" />
      case 'warning': return <AlertTriangle size={16} className="text-yellow-500" />
      default: return <Info size={16} className="text-blue-500" />
    }
  }

  const getColor = (type: string) => {
    switch (type) {
      case 'success': return 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950'
      case 'error': return 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950'
      case 'warning': return 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950'
      default: return 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950'
    }
  }

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={cn(
            "flex items-start space-x-3 p-4 rounded-lg border shadow-lg transition-all duration-300",
            getColor(notification.type)
          )}
        >
          {getIcon(notification.type)}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">
              {notification.message}
            </p>
          </div>
          <button
            onClick={() => removeNotification(notification.id)}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}