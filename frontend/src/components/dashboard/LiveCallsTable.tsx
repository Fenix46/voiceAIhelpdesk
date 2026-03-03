import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { 
  Phone,
  PhoneCall,
  Clock,
  User,
  Tag,
  AlertCircle,
  CheckCircle,
  Pause,
  Play,
  MoreHorizontal,
  ExternalLink,
  MessageSquare,
  Volume2,
  VolumeX,
  Users
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface LiveCall {
  callId: string
  customerName: string
  customerPhone: string
  operatorName: string
  status: 'active' | 'on-hold' | 'transferring' | 'escalating'
  category: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  duration: number // seconds
  startTime: Date
  lastActivity: Date
  sentiment?: 'positive' | 'neutral' | 'negative'
  confidence?: number
  currentIntent?: string
  audioLevel?: number // 0-1
  isRecording: boolean
  isMuted: boolean
  transferTarget?: string
  escalationReason?: string
  notes?: string
}

interface LiveCallsTableProps {
  data: LiveCall[]
  onCallAction?: (callId: string, action: string) => void
  onCallSelect?: (callId: string) => void
  refreshInterval?: number
  maxRows?: number
  className?: string
}

export function LiveCallsTable({
  data,
  onCallAction,
  onCallSelect,
  refreshInterval = 5000,
  maxRows = 10,
  className
}: LiveCallsTableProps) {
  const [selectedCall, setSelectedCall] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'duration' | 'priority' | 'startTime'>('duration')
  const [filterStatus, setFilterStatus] = useState<'all' | LiveCall['status']>('all')
  const [showDetails, setShowDetails] = useState(false)

  // Filter and sort data
  const processedData = useMemo(() => {
    let filtered = filterStatus === 'all' 
      ? data 
      : data.filter(call => call.status === filterStatus)

    // Sort by selected criteria
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'duration':
          return b.duration - a.duration
        case 'priority':
          const priorityOrder = { urgent: 4, high: 3, medium: 2, low: 1 }
          return priorityOrder[b.priority] - priorityOrder[a.priority]
        case 'startTime':
          return b.startTime.getTime() - a.startTime.getTime()
        default:
          return 0
      }
    })

    return filtered.slice(0, maxRows)
  }, [data, filterStatus, sortBy, maxRows])

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getStatusColor = (status: LiveCall['status']) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100 dark:bg-green-900/20'
      case 'on-hold': return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20'
      case 'transferring': return 'text-blue-600 bg-blue-100 dark:bg-blue-900/20'
      case 'escalating': return 'text-red-600 bg-red-100 dark:bg-red-900/20'
      default: return 'text-gray-600 bg-gray-100 dark:bg-gray-900/20'
    }
  }

  const getPriorityColor = (priority: LiveCall['priority']) => {
    switch (priority) {
      case 'urgent': return 'text-red-600'
      case 'high': return 'text-orange-600'
      case 'medium': return 'text-yellow-600'
      case 'low': return 'text-green-600'
      default: return 'text-gray-600'
    }
  }

  const getSentimentIcon = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return <CheckCircle size={14} className="text-green-500" />
      case 'negative': return <AlertCircle size={14} className="text-red-500" />
      default: return <AlertCircle size={14} className="text-gray-500" />
    }
  }

  const getStatusIcon = (status: LiveCall['status']) => {
    switch (status) {
      case 'active': return <Phone size={14} className="text-green-500" />
      case 'on-hold': return <Pause size={14} className="text-yellow-500" />
      case 'transferring': return <ExternalLink size={14} className="text-blue-500" />
      case 'escalating': return <AlertCircle size={14} className="text-red-500" />
      default: return <Phone size={14} className="text-gray-500" />
    }
  }

  if (data.length === 0) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <Phone size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
        <h3 className="font-medium mb-2">No Active Calls</h3>
        <p className="text-sm text-muted-foreground">
          Live calls will appear here when agents are active.
        </p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <PhoneCall size={20} className="text-primary" />
            <span>Live Calls</span>
            <span className="text-sm bg-primary/10 text-primary px-2 py-1 rounded-full">
              {data.length}
            </span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Real-time view of active customer calls
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          {/* Status Filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="on-hold">On Hold</option>
            <option value="transferring">Transferring</option>
            <option value="escalating">Escalating</option>
          </select>

          {/* Sort Options */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="duration">Duration</option>
            <option value="priority">Priority</option>
            <option value="startTime">Start Time</option>
          </select>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? 'Simple' : 'Detailed'}
          </Button>
        </div>
      </div>

      {/* Calls Table */}
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr className="text-left text-sm">
                <th className="p-3 font-medium">Customer</th>
                <th className="p-3 font-medium">Operator</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">Duration</th>
                <th className="p-3 font-medium">Priority</th>
                {showDetails && <th className="p-3 font-medium">Sentiment</th>}
                {showDetails && <th className="p-3 font-medium">Category</th>}
                <th className="p-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {processedData.map((call, index) => (
                <motion.tr
                  key={call.callId}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className={cn(
                    "border-t hover:bg-muted/30 transition-colors cursor-pointer",
                    selectedCall === call.callId && "bg-primary/5 border-primary/20"
                  )}
                  onClick={() => {
                    setSelectedCall(selectedCall === call.callId ? null : call.callId)
                    onCallSelect?.(call.callId)
                  }}
                >
                  <td className="p-3">
                    <div className="flex items-center space-x-3">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{call.customerName}</div>
                        <div className="text-sm text-muted-foreground truncate">
                          {call.customerPhone}
                        </div>
                      </div>
                      {/* Audio Level Indicator */}
                      {call.audioLevel !== undefined && (
                        <div className="flex items-center space-x-1">
                          {call.isMuted ? (
                            <VolumeX size={14} className="text-gray-400" />
                          ) : (
                            <>
                              <Volume2 size={14} className="text-gray-600" />
                              <div className="w-8 bg-muted rounded-full h-1">
                                <div 
                                  className="h-1 bg-green-500 rounded-full transition-all"
                                  style={{ width: `${call.audioLevel * 100}%` }}
                                />
                              </div>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className="flex items-center space-x-2">
                      <User size={14} className="text-muted-foreground" />
                      <span className="font-medium">{call.operatorName}</span>
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className={cn(
                      "inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium",
                      getStatusColor(call.status)
                    )}>
                      {getStatusIcon(call.status)}
                      <span className="capitalize">{call.status.replace('-', ' ')}</span>
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className="flex items-center space-x-2">
                      <Clock size={14} className="text-muted-foreground" />
                      <span className="font-mono text-sm">{formatDuration(call.duration)}</span>
                      {call.isRecording && (
                        <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                      )}
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <span className={cn("font-medium capitalize", getPriorityColor(call.priority))}>
                      {call.priority}
                    </span>
                  </td>
                  
                  {showDetails && (
                    <td className="p-3">
                      <div className="flex items-center space-x-2">
                        {getSentimentIcon(call.sentiment)}
                        <span className="text-sm capitalize">{call.sentiment || 'unknown'}</span>
                        {call.confidence && (
                          <span className="text-xs text-muted-foreground">
                            ({(call.confidence * 100).toFixed(0)}%)
                          </span>
                        )}
                      </div>
                    </td>
                  )}
                  
                  {showDetails && (
                    <td className="p-3">
                      <div className="flex items-center space-x-2">
                        <Tag size={14} className="text-muted-foreground" />
                        <span className="text-sm truncate">{call.category}</span>
                      </div>
                    </td>
                  )}
                  
                  <td className="p-3">
                    <div className="flex items-center space-x-1">
                      {call.status === 'active' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation()
                            onCallAction?.(call.callId, 'hold')
                          }}
                        >
                          <Pause size={12} />
                        </Button>
                      )}
                      
                      {call.status === 'on-hold' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation()
                            onCallAction?.(call.callId, 'resume')
                          }}
                        >
                          <Play size={12} />
                        </Button>
                      )}
                      
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onCallAction?.(call.callId, 'transfer')
                        }}
                      >
                        <ExternalLink size={12} />
                      </Button>
                      
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onCallAction?.(call.callId, 'more')
                        }}
                      >
                        <MoreHorizontal size={12} />
                      </Button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected Call Details */}
      {selectedCall && showDetails && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="p-4 bg-muted/20 rounded-lg"
        >
          {(() => {
            const call = data.find(c => c.callId === selectedCall)
            if (!call) return null
            
            return (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium">Call Details - {call.customerName}</h4>
                  <span className="text-sm text-muted-foreground">#{call.callId.slice(0, 8)}</span>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Started:</span>
                    <div className="font-medium">{call.startTime.toLocaleTimeString()}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Last Activity:</span>
                    <div className="font-medium">{call.lastActivity.toLocaleTimeString()}</div>
                  </div>
                  {call.currentIntent && (
                    <div>
                      <span className="text-muted-foreground">Intent:</span>
                      <div className="font-medium">{call.currentIntent}</div>
                    </div>
                  )}
                  {call.transferTarget && (
                    <div>
                      <span className="text-muted-foreground">Transfer To:</span>
                      <div className="font-medium">{call.transferTarget}</div>
                    </div>
                  )}
                </div>
                
                {call.notes && (
                  <div>
                    <span className="text-muted-foreground text-sm">Notes:</span>
                    <div className="mt-1 p-2 bg-background rounded text-sm">{call.notes}</div>
                  </div>
                )}
                
                {call.escalationReason && (
                  <div className="p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 rounded">
                    <div className="flex items-center space-x-2 text-red-800 dark:text-red-200">
                      <AlertCircle size={16} />
                      <span className="font-medium">Escalation Reason:</span>
                    </div>
                    <p className="text-sm text-red-700 dark:text-red-300 mt-1">{call.escalationReason}</p>
                  </div>
                )}
              </div>
            )
          })()}
        </motion.div>
      )}

      {/* Summary Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold">{data.filter(c => c.status === 'active').length}</div>
          <div className="text-sm text-muted-foreground">Active</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold">{data.filter(c => c.status === 'on-hold').length}</div>
          <div className="text-sm text-muted-foreground">On Hold</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold">
            {Math.round(data.reduce((sum, call) => sum + call.duration, 0) / data.length / 60) || 0}min
          </div>
          <div className="text-sm text-muted-foreground">Avg Duration</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold text-red-600">
            {data.filter(c => c.priority === 'urgent' || c.priority === 'high').length}
          </div>
          <div className="text-sm text-muted-foreground">High Priority</div>
        </div>
      </div>
    </div>
  )
}