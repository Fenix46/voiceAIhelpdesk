import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { Button } from '@/components/ui/button'
import { 
  Clock,
  TrendingUp,
  Target,
  AlertTriangle,
  CheckCircle,
  Info
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface ResolutionTimeData {
  ticketId: string
  resolutionTime: number // minutes
  category: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  customerSatisfaction?: number
  resolvedAt: Date
  wasEscalated: boolean
  complexityScore?: number
}

interface ResolutionTimeHistogramProps {
  data: ResolutionTimeData[]
  binSize?: number // minutes per bin
  showPercentiles?: boolean
  showSLA?: boolean
  slaTarget?: number // minutes
  className?: string
}

export function ResolutionTimeHistogram({
  data,
  binSize = 30, // 30 minute bins
  showPercentiles = true,
  showSLA = true,
  slaTarget = 120, // 2 hours
  className
}: ResolutionTimeHistogramProps) {
  const [selectedBin, setSelectedBin] = useState<string | null>(null)
  const [filterPriority, setFilterPriority] = useState<string>('all')
  const [timeUnit, setTimeUnit] = useState<'minutes' | 'hours'>('minutes')

  // Filter data based on priority
  const filteredData = useMemo(() => {
    return filterPriority === 'all' 
      ? data 
      : data.filter(item => item.priority === filterPriority)
  }, [data, filterPriority])

  // Create histogram bins
  const histogramData = useMemo(() => {
    if (filteredData.length === 0) return []

    const maxTime = Math.max(...filteredData.map(d => d.resolutionTime))
    const numBins = Math.ceil(maxTime / binSize)
    
    const bins = Array.from({ length: numBins }, (_, i) => {
      const start = i * binSize
      const end = (i + 1) * binSize
      const binData = filteredData.filter(d => d.resolutionTime >= start && d.resolutionTime < end)
      
      return {
        binLabel: timeUnit === 'hours' 
          ? `${(start/60).toFixed(1)}-${(end/60).toFixed(1)}h`
          : `${start}-${end}m`,
        start,
        end,
        count: binData.length,
        percentage: (binData.length / filteredData.length) * 100,
        avgSatisfaction: binData.length > 0 
          ? binData.filter(d => d.customerSatisfaction).reduce((sum, d) => sum + d.customerSatisfaction!, 0) / binData.filter(d => d.customerSatisfaction).length || 0
          : 0,
        escalatedCount: binData.filter(d => d.wasEscalated).length,
        tickets: binData
      }
    }).filter(bin => bin.count > 0)

    return bins
  }, [filteredData, binSize, timeUnit])

  // Calculate statistics
  const stats = useMemo(() => {
    if (filteredData.length === 0) return null

    const times = filteredData.map(d => d.resolutionTime).sort((a, b) => a - b)
    const n = times.length
    
    const mean = times.reduce((sum, time) => sum + time, 0) / n
    const median = n % 2 === 0 ? (times[n/2 - 1] + times[n/2]) / 2 : times[Math.floor(n/2)]
    const p75 = times[Math.floor(n * 0.75)]
    const p90 = times[Math.floor(n * 0.90)]
    const p95 = times[Math.floor(n * 0.95)]
    
    const withinSLA = filteredData.filter(d => d.resolutionTime <= slaTarget).length
    const slaCompliance = (withinSLA / filteredData.length) * 100
    
    const escalated = filteredData.filter(d => d.wasEscalated).length
    const escalationRate = (escalated / filteredData.length) * 100

    return {
      mean,
      median,
      p75,
      p90,
      p95,
      slaCompliance,
      escalationRate,
      totalTickets: filteredData.length,
      withinSLA,
      escalated
    }
  }, [filteredData, slaTarget])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-card border rounded-lg p-3 shadow-lg">
          <p className="font-medium mb-2">{label}</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between space-x-4">
              <span>Tickets:</span>
              <span className="font-medium">{data.count}</span>
            </div>
            <div className="flex justify-between space-x-4">
              <span>Percentage:</span>
              <span className="font-medium">{data.percentage.toFixed(1)}%</span>
            </div>
            {data.avgSatisfaction > 0 && (
              <div className="flex justify-between space-x-4">
                <span>Avg Satisfaction:</span>
                <span className="font-medium">{data.avgSatisfaction.toFixed(1)}/5</span>
              </div>
            )}
            {data.escalatedCount > 0 && (
              <div className="flex justify-between space-x-4">
                <span>Escalated:</span>
                <span className="font-medium text-orange-600">{data.escalatedCount}</span>
              </div>
            )}
          </div>
        </div>
      )
    }
    return null
  }

  if (!stats || histogramData.length === 0) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <Clock size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
        <h3 className="font-medium mb-2">No Resolution Time Data</h3>
        <p className="text-sm text-muted-foreground">
          Resolution time analysis will appear here once tickets are resolved.
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
            <Clock size={20} className="text-primary" />
            <span>Resolution Time Distribution</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Analysis of ticket resolution times and patterns
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          {/* Time Unit Toggle */}
          <div className="flex space-x-1 bg-muted rounded-lg p-1">
            <button
              onClick={() => setTimeUnit('minutes')}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors",
                timeUnit === 'minutes'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              Minutes
            </button>
            <button
              onClick={() => setTimeUnit('hours')}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors",
                timeUnit === 'hours'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              Hours
            </button>
          </div>

          {/* Priority Filter */}
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="all">All Priorities</option>
            <option value="low">Low Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="high">High Priority</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
      </div>

      {/* Key Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">
            {timeUnit === 'hours' ? (stats.mean / 60).toFixed(1) : stats.mean.toFixed(0)}
            <span className="text-sm text-muted-foreground ml-1">
              {timeUnit === 'hours' ? 'h' : 'm'}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">Mean Time</div>
        </div>

        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">
            {timeUnit === 'hours' ? (stats.median / 60).toFixed(1) : stats.median.toFixed(0)}
            <span className="text-sm text-muted-foreground ml-1">
              {timeUnit === 'hours' ? 'h' : 'm'}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">Median Time</div>
        </div>

        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">
            {timeUnit === 'hours' ? (stats.p90 / 60).toFixed(1) : stats.p90.toFixed(0)}
            <span className="text-sm text-muted-foreground ml-1">
              {timeUnit === 'hours' ? 'h' : 'm'}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">90th Percentile</div>
        </div>

        <div className="p-4 bg-card border rounded-lg text-center">
          <div className={cn(
            "text-2xl font-bold",
            stats.slaCompliance >= 90 ? "text-green-600" : 
            stats.slaCompliance >= 80 ? "text-yellow-600" : "text-red-600"
          )}>
            {stats.slaCompliance.toFixed(1)}%
          </div>
          <div className="text-sm text-muted-foreground">SLA Compliance</div>
        </div>

        <div className="p-4 bg-card border rounded-lg text-center">
          <div className={cn(
            "text-2xl font-bold",
            stats.escalationRate < 10 ? "text-green-600" : 
            stats.escalationRate < 20 ? "text-yellow-600" : "text-red-600"
          )}>
            {stats.escalationRate.toFixed(1)}%
          </div>
          <div className="text-sm text-muted-foreground">Escalation Rate</div>
        </div>

        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">{stats.totalTickets}</div>
          <div className="text-sm text-muted-foreground">Total Tickets</div>
        </div>
      </div>

      {/* SLA Performance Indicator */}
      {showSLA && (
        <div className={cn(
          "p-4 rounded-lg border-l-4",
          stats.slaCompliance >= 90 
            ? "bg-green-50 border-green-500 dark:bg-green-900/10"
            : stats.slaCompliance >= 80 
            ? "bg-yellow-50 border-yellow-500 dark:bg-yellow-900/10"
            : "bg-red-50 border-red-500 dark:bg-red-900/10"
        )}>
          <div className="flex items-start space-x-3">
            {stats.slaCompliance >= 90 ? (
              <CheckCircle size={20} className="text-green-600 mt-0.5" />
            ) : stats.slaCompliance >= 80 ? (
              <AlertTriangle size={20} className="text-yellow-600 mt-0.5" />
            ) : (
              <AlertTriangle size={20} className="text-red-600 mt-0.5" />
            )}
            <div>
              <h4 className="font-medium mb-1">
                SLA Performance: {stats.slaCompliance.toFixed(1)}%
              </h4>
              <p className="text-sm text-muted-foreground">
                {stats.withinSLA} of {stats.totalTickets} tickets resolved within {slaTarget}min target. 
                {stats.slaCompliance < 90 && ` ${(90 - stats.slaCompliance).toFixed(1)}% improvement needed to reach 90% target.`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Histogram Chart */}
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={histogramData}>
            <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
            <XAxis 
              dataKey="binLabel" 
              tick={{ fontSize: 12 }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            
            <Bar 
              dataKey="count" 
              fill="#3b82f6"
              radius={[4, 4, 0, 0]}
              onClick={(data) => setSelectedBin(
                selectedBin === data.binLabel ? null : data.binLabel
              )}
            />
            
            {/* SLA Target Line */}
            {showSLA && (
              <ReferenceLine 
                x={histogramData.find(bin => 
                  bin.start <= slaTarget && bin.end > slaTarget
                )?.binLabel}
                stroke="#ef4444"
                strokeDasharray="5 5"
                label={{ value: "SLA Target", position: "top" }}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Percentile Markers */}
      {showPercentiles && (
        <div className="grid grid-cols-3 gap-4">
          <div className="p-3 bg-muted/20 rounded-lg text-center">
            <div className="font-medium">
              P75: {timeUnit === 'hours' ? (stats.p75 / 60).toFixed(1) : stats.p75.toFixed(0)}
              {timeUnit === 'hours' ? 'h' : 'm'}
            </div>
            <div className="text-xs text-muted-foreground">75% resolved by</div>
          </div>
          <div className="p-3 bg-muted/20 rounded-lg text-center">
            <div className="font-medium">
              P90: {timeUnit === 'hours' ? (stats.p90 / 60).toFixed(1) : stats.p90.toFixed(0)}
              {timeUnit === 'hours' ? 'h' : 'm'}
            </div>
            <div className="text-xs text-muted-foreground">90% resolved by</div>
          </div>
          <div className="p-3 bg-muted/20 rounded-lg text-center">
            <div className="font-medium">
              P95: {timeUnit === 'hours' ? (stats.p95 / 60).toFixed(1) : stats.p95.toFixed(0)}
              {timeUnit === 'hours' ? 'h' : 'm'}
            </div>
            <div className="text-xs text-muted-foreground">95% resolved by</div>
          </div>
        </div>
      )}

      {/* Selected Bin Details */}
      {selectedBin && (
        <div className="mt-6 p-4 bg-muted/20 rounded-lg">
          <h4 className="font-medium mb-3 flex items-center space-x-2">
            <Target size={16} />
            <span>Tickets in {selectedBin} Range</span>
          </h4>
          
          {(() => {
            const bin = histogramData.find(b => b.binLabel === selectedBin)
            if (!bin) return null
            
            return (
              <div className="space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Count:</span>
                    <span className="ml-2 font-medium">{bin.count}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Percentage:</span>
                    <span className="ml-2 font-medium">{bin.percentage.toFixed(1)}%</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Escalated:</span>
                    <span className="ml-2 font-medium">{bin.escalatedCount}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Avg Satisfaction:</span>
                    <span className="ml-2 font-medium">{bin.avgSatisfaction.toFixed(1)}/5</span>
                  </div>
                </div>
                
                <div className="text-xs text-muted-foreground">
                  {bin.tickets.length > 5 ? 
                    `Showing distribution for ${bin.tickets.length} tickets in this time range` :
                    `Sample tickets: ${bin.tickets.map(t => `#${t.ticketId.slice(0, 8)}`).join(', ')}`
                  }
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}