import { useOffline } from '@/hooks/useOffline'
import { Button } from '@/components/ui/button'
import { 
  WifiOff, 
  Wifi, 
  RefreshCw, 
  Download,
  Upload,
  X,
  Clock
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

export function OfflineBanner() {
  const { 
    isOnline, 
    offlineQueue, 
    isProcessingQueue,
    processOfflineQueue,
    clearOfflineQueue,
    hasOfflineChanges
  } = useOffline()
  
  const [isExpanded, setIsExpanded] = useState(false)
  const [isDismissed, setIsDismissed] = useState(false)

  // Don't show banner if dismissed and no offline changes
  if (isDismissed && !hasOfflineChanges) return null

  const handleSync = () => {
    processOfflineQueue()
  }

  const handleDismiss = () => {
    if (!hasOfflineChanges) {
      setIsDismissed(true)
    }
  }

  return (
    <div className={cn(
      "border-b transition-all duration-300",
      !isOnline 
        ? "bg-orange-50 dark:bg-orange-950/20 border-orange-200 dark:border-orange-800"
        : hasOfflineChanges
        ? "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800"
        : "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800"
    )}>
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Status Info */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              {!isOnline ? (
                <WifiOff size={20} className="text-orange-600 dark:text-orange-400" />
              ) : isProcessingQueue ? (
                <RefreshCw size={20} className="text-blue-600 dark:text-blue-400 animate-spin" />
              ) : (
                <Wifi size={20} className="text-green-600 dark:text-green-400" />
              )}
              
              <span className={cn(
                "font-medium",
                !isOnline 
                  ? "text-orange-800 dark:text-orange-200"
                  : hasOfflineChanges
                  ? "text-blue-800 dark:text-blue-200"
                  : "text-green-800 dark:text-green-200"
              )}>
                {!isOnline 
                  ? "You're offline"
                  : isProcessingQueue
                  ? "Syncing changes..."
                  : hasOfflineChanges
                  ? "You have offline changes"
                  : "You're online"
                }
              </span>
            </div>

            {hasOfflineChanges && (
              <div className="flex items-center space-x-1 text-sm text-muted-foreground">
                <Clock size={14} />
                <span>{offlineQueue.length} item{offlineQueue.length !== 1 ? 's' : ''} pending</span>
              </div>
            )}

            {!isOnline && (
              <p className="text-sm text-orange-700 dark:text-orange-300">
                Changes will be saved locally and synced when connection is restored
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center space-x-2">
            {hasOfflineChanges && isOnline && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSync}
                disabled={isProcessingQueue}
                className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-200"
              >
                <Upload size={16} className="mr-1" />
                Sync Now
              </Button>
            )}

            {hasOfflineChanges && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-muted-foreground hover:text-foreground"
              >
                {isExpanded ? 'Hide' : 'Show'} Details
              </Button>
            )}

            {!hasOfflineChanges && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDismiss}
                className="text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </Button>
            )}
          </div>
        </div>

        {/* Expanded Details */}
        {isExpanded && hasOfflineChanges && (
          <div className="mt-4 pt-4 border-t border-current/20">
            <div className="space-y-3">
              <h4 className="font-medium text-sm">Offline Changes:</h4>
              <div className="space-y-2">
                {offlineQueue.slice(0, 5).map((item) => (
                  <div 
                    key={item.id}
                    className="flex items-center justify-between text-sm bg-background/50 rounded p-2"
                  >
                    <div className="flex items-center space-x-2">
                      <div className={cn(
                        "w-2 h-2 rounded-full",
                        item.type === 'conversation' ? "bg-blue-500" :
                        item.type === 'ticket' ? "bg-green-500" : "bg-purple-500"
                      )} />
                      <span className="capitalize">{item.type}</span>
                      {item.retryCount > 0 && (
                        <span className="text-orange-600 text-xs">
                          (Retry {item.retryCount})
                        </span>
                      )}
                    </div>
                    <span className="text-muted-foreground text-xs">
                      {item.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                ))}
                
                {offlineQueue.length > 5 && (
                  <p className="text-xs text-muted-foreground">
                    ...and {offlineQueue.length - 5} more items
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2 pt-2">
                {isOnline && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSync}
                    disabled={isProcessingQueue}
                  >
                    <Upload size={14} className="mr-1" />
                    Sync All
                  </Button>
                )}
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearOfflineQueue}
                  className="text-destructive hover:text-destructive"
                >
                  Clear Queue
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}