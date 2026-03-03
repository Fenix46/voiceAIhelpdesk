import { useState, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { Button } from '@/components/ui/button'
import { 
  TrendingUp, 
  TrendingDown, 
  Calendar,
  Clock,
  Phone,
  Activity
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CallVolumeData {
  timestamp: Date
  totalCalls: number
  inboundCalls: number
  successfulCalls: number
  failedCalls: number
  averageDuration: number
  peakHour?: boolean
}

interface CallVolumeChartProps {
  data: CallVolumeData[]
  timeRange?: '1h' | '6h' | '24h' | '7d' | '30d'
  onTimeRangeChange?: (range: string) => void
  className?: string
}

export function CallVolumeChart({
  data,
  timeRange = '24h',
  onTimeRangeChange,
  className
}: CallVolumeChartProps) {
  const [chartType, setChartType] = useState<'line' | 'area'>('area')
  const [focusMetric, setFocusMetric] = useState<'total' | 'successful' | 'failed'>('total')

  // Process data for chart display
  const chartData = useMemo(() => {
    return data.map(point => ({
      time: point.timestamp.toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit',
        ...(timeRange === '7d' || timeRange === '30d' ? { 
          month: 'short', 
          day: 'numeric' 
        } : {})
      }),
      timestamp: point.timestamp,
      total: point.totalCalls,
      inbound: point.inboundCalls,
      successful: point.successfulCalls,
      failed: point.failedCalls,
      duration: point.averageDuration,
      isPeak: point.peakHour
    }))
  }, [data, timeRange])

  // Calculate statistics
  const stats = useMemo(() => {
    if (data.length === 0) return null

    const totalCalls = data.reduce((sum, point) => sum + point.totalCalls, 0)
    const successfulCalls = data.reduce((sum, point) => sum + point.successfulCalls, 0)
    const failedCalls = data.reduce((sum, point) => sum + point.failedCalls, 0)
    const avgDuration = data.reduce((sum, point) => sum + point.averageDuration, 0) / data.length

    const successRate = totalCalls > 0 ? (successfulCalls / totalCalls) * 100 : 0
    
    // Calculate trend (comparing first half vs second half)
    const midpoint = Math.floor(data.length / 2)
    const firstHalf = data.slice(0, midpoint)
    const secondHalf = data.slice(midpoint)
    
    const firstHalfAvg = firstHalf.reduce((sum, point) => sum + point.totalCalls, 0) / firstHalf.length
    const secondHalfAvg = secondHalf.reduce((sum, point) => sum + point.totalCalls, 0) / secondHalf.length
    
    const trend = secondHalfAvg > firstHalfAvg ? 'up' : secondHalfAvg < firstHalfAvg ? 'down' : 'stable'
    const trendPercentage = Math.abs(((secondHalfAvg - firstHalfAvg) / firstHalfAvg) * 100)

    return {
      totalCalls,
      successfulCalls,
      failedCalls,
      successRate,
      avgDuration,
      trend,
      trendPercentage
    }
  }, [data])

  const timeRanges = [
    { value: '1h', label: '1 Hour' },
    { value: '6h', label: '6 Hours' },
    { value: '24h', label: '24 Hours' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' }
  ]

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-card border rounded-lg p-3 shadow-lg">
          <p className="font-medium mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center space-x-2 text-sm">
              <div 
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="capitalize">{entry.dataKey}:</span>
              <span className="font-medium">{entry.value}</span>
            </div>
          ))}
        </div>
      )
    }
    return null
  }

  if (!stats || chartData.length === 0) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <Phone size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
        <h3 className="font-medium mb-2">No Call Data</h3>
        <p className="text-sm text-muted-foreground">
          Call volume data will appear here once calls are processed.
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
            <Phone size={20} className="text-primary" />
            <span>Call Volume</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Call patterns and volume trends over time
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          {/* Chart Type Toggle */}
          <div className="flex space-x-1 bg-muted rounded-lg p-1">
            <button
              onClick={() => setChartType('area')}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors",
                chartType === 'area'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              Area
            </button>
            <button
              onClick={() => setChartType('line')}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors",
                chartType === 'line'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              Line
            </button>
          </div>

          {/* Time Range Selector */}
          <select
            value={timeRange}
            onChange={(e) => onTimeRangeChange?.(e.target.value)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            {timeRanges.map(range => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Calls</p>
              <p className="text-2xl font-bold">{stats.totalCalls.toLocaleString()}</p>
            </div>
            <div className={cn(
              "flex items-center space-x-1 text-sm",
              stats.trend === 'up' ? "text-green-600" : 
              stats.trend === 'down' ? "text-red-600" : "text-gray-600"
            )}>
              {stats.trend === 'up' ? <TrendingUp size={14} /> : 
               stats.trend === 'down' ? <TrendingDown size={14} /> : <Activity size={14} />}
              <span>{stats.trendPercentage.toFixed(1)}%</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div>
            <p className="text-sm text-muted-foreground">Success Rate</p>
            <p className="text-2xl font-bold">{stats.successRate.toFixed(1)}%</p>
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div>
            <p className="text-sm text-muted-foreground">Avg Duration</p>
            <p className="text-2xl font-bold">{Math.round(stats.avgDuration)}s</p>
          </div>
        </div>

        <div className="p-4 bg-card border rounded-lg">
          <div>
            <p className="text-sm text-muted-foreground">Failed Calls</p>
            <p className="text-2xl font-bold text-red-600">{stats.failedCalls}</p>
          </div>
        </div>
      </div>

      {/* Metric Focus Selector */}
      <div className="flex items-center space-x-2">
        <span className="text-sm text-muted-foreground">Focus on:</span>
        <div className="flex space-x-1 bg-muted rounded-lg p-1">
          {[
            { value: 'total', label: 'Total Calls', color: '#3b82f6' },
            { value: 'successful', label: 'Successful', color: '#22c55e' },
            { value: 'failed', label: 'Failed', color: '#ef4444' }
          ].map(metric => (
            <button
              key={metric.value}
              onClick={() => setFocusMetric(metric.value as any)}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors flex items-center space-x-1",
                focusMetric === metric.value
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              <div 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: metric.color }}
              />
              <span>{metric.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'area' ? (
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis 
                dataKey="time" 
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              
              {focusMetric === 'total' && (
                <>
                  <Area
                    type="monotone"
                    dataKey="total"
                    stackId="1"
                    stroke="#3b82f6"
                    fill="#3b82f6"
                    fillOpacity={0.3}
                  />
                  <Area
                    type="monotone"
                    dataKey="successful"
                    stackId="2"
                    stroke="#22c55e"
                    fill="#22c55e"
                    fillOpacity={0.2}
                  />
                </>
              )}
              
              {focusMetric === 'successful' && (
                <Area
                  type="monotone"
                  dataKey="successful"
                  stroke="#22c55e"
                  fill="#22c55e"
                  fillOpacity={0.3}
                />
              )}
              
              {focusMetric === 'failed' && (
                <Area
                  type="monotone"
                  dataKey="failed"
                  stroke="#ef4444"
                  fill="#ef4444"
                  fillOpacity={0.3}
                />
              )}
            </AreaChart>
          ) : (
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis 
                dataKey="time" 
                tick={{ fontSize: 12 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              
              {focusMetric === 'total' && (
                <>
                  <Line
                    type="monotone"
                    dataKey="total"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="successful"
                    stroke="#22c55e"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                </>
              )}
              
              {focusMetric === 'successful' && (
                <Line
                  type="monotone"
                  dataKey="successful"
                  stroke="#22c55e"
                  strokeWidth={3}
                  dot={false}
                />
              )}
              
              {focusMetric === 'failed' && (
                <Line
                  type="monotone"
                  dataKey="failed"
                  stroke="#ef4444"
                  strokeWidth={3}
                  dot={false}
                />
              )}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Peak Hours Indicator */}
      {chartData.some(point => point.isPeak) && (
        <div className="p-3 bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800 rounded-lg">
          <div className="flex items-center space-x-2">
            <Clock size={16} className="text-orange-600" />
            <span className="text-sm font-medium text-orange-800 dark:text-orange-200">
              Peak Hours Detected
            </span>
          </div>
          <p className="text-xs text-orange-700 dark:text-orange-300 mt-1">
            Higher than average call volume during highlighted periods
          </p>
        </div>
      )}
    </div>
  )
}