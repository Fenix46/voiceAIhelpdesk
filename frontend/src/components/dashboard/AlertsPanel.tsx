import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  AlertTriangle,
  AlertCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Shield,
  Zap,
  Bell,
  BellOff,
  X,
  CheckCircle,
  Info,
  Settings,
  Filter,
  RefreshCw,
  ExternalLink
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Alert {
  id: string
  title: string
  message: string
  type: 'critical' | 'warning' | 'info' | 'success'
  category: 'performance' | 'security' | 'system' | 'quality' | 'capacity'
  severity: 1 | 2 | 3 | 4 | 5 // 1 = lowest, 5 = highest
  timestamp: Date
  acknowledged: boolean
  resolved: boolean
  source: string
  affectedItems?: string[]
  metrics?: Record<string, number>
  actionRequired?: boolean
  autoResolve?: boolean
  resolvedAt?: Date
  acknowledgedBy?: string
  relatedAlerts?: string[]
}

interface AlertsPanelProps {
  alerts: Alert[]
  onAlertAcknowledge?: (alertId: string) => void
  onAlertResolve?: (alertId: string) => void
  onAlertDismiss?: (alertId: string) => void
  onAlertClick?: (alertId: string) => void
  showResolved?: boolean
  maxAlerts?: number
  autoRefresh?: boolean
  className?: string
}

export function AlertsPanel({
  alerts,
  onAlertAcknowledge,
  onAlertResolve,
  onAlertDismiss,
  onAlertClick,
  showResolved = false,
  maxAlerts = 20,
  autoRefresh = true,
  className
}: AlertsPanelProps) {
  const [filterType, setFilterType] = useState<Alert['type'] | 'all'>('all')
  const [filterCategory, setFilterCategory] = useState<Alert['category'] | 'all'>('all')
  const [sortBy, setSortBy] = useState<'timestamp' | 'severity' | 'type'>('severity')
  const [mutedAlerts, setMutedAlerts] = useState<Set<string>>(new Set())
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null)

  // Process alerts
  const processedAlerts = useMemo(() => {
    let filtered = alerts.filter(alert => {
      if (!showResolved && alert.resolved) return false
      if (filterType !== 'all' && alert.type !== filterType) return false
      if (filterCategory !== 'all' && alert.category !== filterCategory) return false
      return true
    })

    // Sort alerts
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'severity':
          if (a.severity !== b.severity) return b.severity - a.severity
          return b.timestamp.getTime() - a.timestamp.getTime()
        case 'timestamp':
          return b.timestamp.getTime() - a.timestamp.getTime()
        case 'type':
          if (a.type !== b.type) return a.type.localeCompare(b.type)
          return b.severity - a.severity
        default:
          return 0
      }
    })

    return filtered.slice(0, maxAlerts)
  }, [alerts, showResolved, filterType, filterCategory, sortBy, maxAlerts])

  // Calculate statistics
  const stats = useMemo(() => {
    const activeAlerts = alerts.filter(a => !a.resolved)
    const criticalCount = activeAlerts.filter(a => a.type === 'critical').length
    const warningCount = activeAlerts.filter(a => a.type === 'warning').length
    const unacknowledgedCount = activeAlerts.filter(a => !a.acknowledged).length
    const actionRequiredCount = activeAlerts.filter(a => a.actionRequired).length

    return {
      total: activeAlerts.length,
      critical: criticalCount,
      warning: warningCount,
      unacknowledged: unacknowledgedCount,
      actionRequired: actionRequiredCount
    }
  }, [alerts])

  const getAlertIcon = (type: Alert['type']) => {
    switch (type) {
      case 'critical': return <AlertTriangle size={16} className="text-red-500" />
      case 'warning': return <AlertCircle size={16} className="text-yellow-500" />
      case 'info': return <Info size={16} className="text-blue-500" />
      case 'success': return <CheckCircle size={16} className="text-green-500" />
      default: return <AlertCircle size={16} className="text-gray-500" />
    }
  }

  const getCategoryIcon = (category: Alert['category']) => {
    switch (category) {
      case 'performance': return <TrendingDown size={14} className="text-orange-500" />
      case 'security': return <Shield size={14} className="text-red-500" />
      case 'system': return <Zap size={14} className="text-blue-500" />
      case 'quality': return <CheckCircle size={14} className="text-green-500" />
      case 'capacity': return <TrendingUp size={14} className="text-purple-500" />
      default: return <Info size={14} className="text-gray-500" />
    }
  }

  const getAlertColor = (type: Alert['type'], resolved = false) => {
    if (resolved) return 'border-l-gray-400 bg-gray-50 dark:bg-gray-900/10'
    
    switch (type) {
      case 'critical': return 'border-l-red-500 bg-red-50 dark:bg-red-900/10'
      case 'warning': return 'border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10'
      case 'info': return 'border-l-blue-500 bg-blue-50 dark:bg-blue-900/10'
      case 'success': return 'border-l-green-500 bg-green-50 dark:bg-green-900/10'
      default: return 'border-l-gray-500 bg-gray-50 dark:bg-gray-900/10'
    }
  }

  const getSeverityBadge = (severity: number) => {
    const colors = [
      'bg-gray-100 text-gray-800',
      'bg-green-100 text-green-800', 
      'bg-yellow-100 text-yellow-800',
      'bg-orange-100 text-orange-800',
      'bg-red-100 text-red-800'
    ]
    return colors[severity - 1] || colors[0]
  }

  const formatTimeAgo = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  const handleMuteAlert = (alertId: string) => {
    const newMuted = new Set(mutedAlerts)
    if (mutedAlerts.has(alertId)) {
      newMuted.delete(alertId)
    } else {
      newMuted.add(alertId)
    }
    setMutedAlerts(newMuted)
  }

  if (alerts.length === 0) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <CheckCircle size={48} className="mx-auto mb-4 text-green-500 opacity-50" />
        <h3 className="font-medium mb-2">No Active Alerts</h3>
        <p className="text-sm text-muted-foreground">
          All systems are operating normally. New alerts will appear here.
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
            <Bell size={20} className="text-primary" />
            <span>System Alerts</span>
            {stats.total > 0 && (
              <span className={cn(
                "text-sm px-2 py-1 rounded-full",
                stats.critical > 0 
                  ? "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300"
                  : stats.warning > 0
                  ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300"
                  : "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-300"
              )}>
                {stats.total}
              </span>
            )}
          </h3>
          <p className="text-sm text-muted-foreground">
            Monitor system health and performance issues
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          {autoRefresh && (
            <div className="flex items-center space-x-1 text-xs text-muted-foreground">
              <RefreshCw size={12} className="animate-spin" />
              <span>Auto-refresh</span>
            </div>
          )}
          
          <Button size="sm" variant="outline">
            <Settings size={14} className="mr-1" />
            Configure
          </Button>
        </div>
      </div>

      {/* Alert Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold">{stats.total}</div>
          <div className="text-xs text-muted-foreground">Total Active</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold text-red-600">{stats.critical}</div>
          <div className="text-xs text-muted-foreground">Critical</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold text-yellow-600">{stats.warning}</div>
          <div className="text-xs text-muted-foreground">Warning</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold">{stats.unacknowledged}</div>
          <div className="text-xs text-muted-foreground">Unacknowledged</div>
        </div>
        <div className="p-3 bg-card border rounded-lg text-center">
          <div className="text-lg font-bold text-orange-600">{stats.actionRequired}</div>
          <div className="text-xs text-muted-foreground">Action Required</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Filter size={16} className="text-muted-foreground" />
          
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Types</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
            <option value="success">Success</option>
          </select>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Categories</option>
            <option value="performance">Performance</option>
            <option value="security">Security</option>
            <option value="system">System</option>
            <option value="quality">Quality</option>
            <option value="capacity">Capacity</option>
          </select>
        </div>

        <div className="flex items-center space-x-2">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="severity">Severity</option>
            <option value="timestamp">Time</option>
            <option value="type">Type</option>
          </select>

          <label className="flex items-center space-x-2 text-sm">
            <input
              type="checkbox"
              checked={showResolved}
              onChange={(e) => setShowResolved?.(e.target.checked)}
              className="rounded"
            />
            <span>Show Resolved</span>
          </label>
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        <AnimatePresence>
          {processedAlerts.map((alert, index) => (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ delay: index * 0.02 }}
              className={cn(
                "border-l-4 rounded-lg transition-all hover:shadow-sm cursor-pointer",
                getAlertColor(alert.type, alert.resolved),
                selectedAlert === alert.id && "ring-2 ring-primary/20",
                mutedAlerts.has(alert.id) && "opacity-50"
              )}
              onClick={() => {
                setSelectedAlert(selectedAlert === alert.id ? null : alert.id)
                onAlertClick?.(alert.id)
              }}
            >
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    <div className="flex-shrink-0 mt-0.5">
                      {getAlertIcon(alert.type)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <h4 className="font-medium text-sm truncate">{alert.title}</h4>
                        
                        <div className="flex items-center space-x-1">
                          {getCategoryIcon(alert.category)}
                          <span className={cn(
                            "text-xs px-1.5 py-0.5 rounded-full font-medium",
                            getSeverityBadge(alert.severity)
                          )}>
                            P{alert.severity}
                          </span>
                        </div>
                      </div>
                      
                      <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                        {alert.message}
                      </p>
                      
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center space-x-4">
                          <div className="flex items-center space-x-1">
                            <Clock size={12} />
                            <span>{formatTimeAgo(alert.timestamp)}</span>
                          </div>
                          
                          <div className="flex items-center space-x-1">
                            <span>Source: {alert.source}</span>
                          </div>
                          
                          {alert.affectedItems && (
                            <div>
                              <span>{alert.affectedItems.length} affected</span>
                            </div>
                          )}
                        </div>
                        
                        <div className="flex items-center space-x-1">
                          {alert.acknowledged && (
                            <span className="text-green-600">✓ Acknowledged</span>
                          )}
                          {alert.resolved && (
                            <span className="text-gray-600">✓ Resolved</span>
                          )}
                          {alert.actionRequired && (
                            <span className="text-orange-600 font-medium">Action Required</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Alert Actions */}
                  <div className="flex items-center space-x-1 ml-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleMuteAlert(alert.id)
                      }}
                    >
                      {mutedAlerts.has(alert.id) ? (
                        <BellOff size={12} />
                      ) : (
                        <Bell size={12} />
                      )}
                    </Button>
                    
                    {!alert.acknowledged && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onAlertAcknowledge?.(alert.id)
                        }}
                      >
                        Ack
                      </Button>
                    )}
                    
                    {!alert.resolved && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          onAlertResolve?.(alert.id)
                        }}
                      >
                        Resolve
                      </Button>
                    )}
                    
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        onAlertDismiss?.(alert.id)
                      }}
                    >
                      <X size={12} />
                    </Button>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Selected Alert Details */}
      {selectedAlert && (
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-4 bg-muted/20 rounded-lg"
          >
            {(() => {
              const alert = alerts.find(a => a.id === selectedAlert)
              if (!alert) return null
              
              return (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">Alert Details</h4>
                    <span className="text-sm text-muted-foreground">#{alert.id.slice(0, 8)}</span>
                  </div>
                  
                  {alert.metrics && Object.keys(alert.metrics).length > 0 && (
                    <div>
                      <h5 className="text-sm font-medium mb-2">Metrics</h5>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {Object.entries(alert.metrics).map(([key, value]) => (
                          <div key={key} className="p-2 bg-background rounded text-center">
                            <div className="font-medium">{value}</div>
                            <div className="text-xs text-muted-foreground capitalize">
                              {key.replace(/([A-Z])/g, ' $1').trim()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {alert.affectedItems && alert.affectedItems.length > 0 && (
                    <div>
                      <h5 className="text-sm font-medium mb-2">Affected Items</h5>
                      <div className="flex flex-wrap gap-1">
                        {alert.affectedItems.map((item, index) => (
                          <span
                            key={index}
                            className="px-2 py-1 bg-primary/10 text-primary text-xs rounded"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {alert.relatedAlerts && alert.relatedAlerts.length > 0 && (
                    <div>
                      <h5 className="text-sm font-medium mb-2">Related Alerts</h5>
                      <div className="space-y-1">
                        {alert.relatedAlerts.map((relatedId, index) => (
                          <div key={index} className="flex items-center space-x-2 text-sm">
                            <ExternalLink size={12} className="text-muted-foreground" />
                            <span>#{relatedId.slice(0, 8)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  <div className="text-xs text-muted-foreground space-y-1">
                    <div>Created: {alert.timestamp.toLocaleString()}</div>
                    {alert.acknowledgedBy && (
                      <div>Acknowledged by: {alert.acknowledgedBy}</div>
                    )}
                    {alert.resolvedAt && (
                      <div>Resolved: {alert.resolvedAt.toLocaleString()}</div>
                    )}
                  </div>
                </div>
              )
            })()}
          </motion.div>
        </AnimatePresence>
      )}

      {/* Bulk Actions */}
      {processedAlerts.filter(a => !a.acknowledged).length > 1 && (
        <div className="flex items-center justify-between p-3 bg-muted/20 rounded-lg">
          <span className="text-sm text-muted-foreground">
            {processedAlerts.filter(a => !a.acknowledged).length} unacknowledged alerts
          </span>
          <div className="flex space-x-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                processedAlerts
                  .filter(a => !a.acknowledged)
                  .forEach(a => onAlertAcknowledge?.(a.id))
              }}
            >
              Acknowledge All
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                processedAlerts
                  .filter(a => a.type !== 'critical')
                  .forEach(a => onAlertDismiss?.(a.id))
              }}
            >
              Dismiss Non-Critical
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}