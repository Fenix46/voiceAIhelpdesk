import { useConversationStore } from '@/store/conversationStore'
import { useAppStore } from '@/store/appStore'
import { socketManager } from '@/lib/socket'
import { 
  Circle,
  Mic,
  MicOff,
  Loader2,
  Wifi,
  WifiOff,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function StatusIndicator() {
  const { isRecording, isProcessing } = useConversationStore()
  const { isOnline } = useAppStore()
  const isConnected = socketManager.isConnected()

  const getStatus = () => {
    if (!isOnline) return { 
      text: 'Offline', 
      color: 'text-red-500',
      bgColor: 'bg-red-500',
      icon: WifiOff 
    }
    
    if (!isConnected) return { 
      text: 'Disconnected', 
      color: 'text-orange-500',
      bgColor: 'bg-orange-500',
      icon: XCircle 
    }
    
    if (isProcessing) return { 
      text: 'Processing', 
      color: 'text-blue-500',
      bgColor: 'bg-blue-500',
      icon: Loader2 
    }
    
    if (isRecording) return { 
      text: 'Recording', 
      color: 'text-red-500',
      bgColor: 'bg-red-500',
      icon: Mic 
    }
    
    return { 
      text: 'Ready', 
      color: 'text-green-500',
      bgColor: 'bg-green-500',
      icon: CheckCircle 
    }
  }

  const status = getStatus()
  const Icon = status.icon

  return (
    <div className="flex items-center space-x-2 text-sm">
      <div className="relative">
        <Circle 
          className={cn("h-3 w-3", status.bgColor)} 
          fill="currentColor"
        />
        {(isRecording || isProcessing) && (
          <div className={cn(
            "absolute inset-0 h-3 w-3 rounded-full animate-ping",
            status.bgColor
          )} />
        )}
      </div>
      <div className="flex items-center space-x-1">
        <Icon 
          size={14} 
          className={cn(
            status.color,
            isProcessing && "animate-spin"
          )} 
        />
        <span className={status.color}>{status.text}</span>
      </div>
    </div>
  )
}