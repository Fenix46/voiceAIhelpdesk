import { useState, useRef, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Activity,
  Play,
  Pause,
  Square,
  Clock,
  Zap,
  Target,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Settings,
  Download,
  RotateCcw,
  Wifi,
  Server,
  Database,
  Monitor,
  Globe,
  Cpu,
  HardDrive,
  Network
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar } from 'recharts'
import { cn } from '@/lib/utils'

interface LatencyMetric {
  timestamp: Date
  totalLatency: number
  breakdown: {
    networkLatency: number
    serverProcessing: number
    audioProcessing: number
    aiInference: number
    responseGeneration: number
    audioSynthesis?: number
  }
  requestSize: number
  responseSize: number
  endpoint: string
  success: boolean
  errorCode?: string
  userAgent?: string
  region?: string
}

interface LatencyTest {
  id: string
  name: string
  description: string
  endpoint: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  payload?: any
  expectedLatency: number // ms
  timeout: number // ms
  iterations: number
  interval: number // ms between requests
  enabled: boolean
}

interface LatencyStats {
  average: number
  median: number
  p95: number
  p99: number
  min: number
  max: number
  standardDeviation: number
  errorRate: number
  throughput: number // requests per second
}

interface LatencyProfilerProps {
  tests: LatencyTest[]
  onTestUpdate?: (test: LatencyTest) => void
  onTestDelete?: (testId: string) => void
  onTestRun?: (testId: string) => Promise<LatencyMetric[]>
  onBulkTest?: (testIds: string[]) => Promise<LatencyMetric[]>
  realTimeMetrics?: LatencyMetric[]
  autoRefresh?: boolean
  className?: string
}

export function LatencyProfiler({
  tests,
  onTestUpdate,
  onTestDelete,
  onTestRun,
  onBulkTest,
  realTimeMetrics = [],
  autoRefresh = false,
  className
}: LatencyProfilerProps) {
  const [isRunning, setIsRunning] = useState(false)
  const [currentTest, setCurrentTest] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<LatencyMetric[]>([])
  const [selectedTests, setSelectedTests] = useState<string[]>([])
  const [progress, setProgress] = useState(0)
  const [currentIteration, setCurrentIteration] = useState(0)
  const [totalIterations, setTotalIterations] = useState(0)
  const [viewMode, setViewMode] = useState<'overview' | 'breakdown' | 'comparison' | 'realtime'>('overview')
  const [timeRange, setTimeRange] = useState<'1m' | '5m' | '15m' | '1h' | '24h'>('5m')
  const [showTestConfig, setShowTestConfig] = useState<string | null>(null)
  const [alertThresholds, setAlertThresholds] = useState({
    latency: 1000, // ms
    errorRate: 5, // %
    p95: 2000 // ms
  })

  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Calculate latency statistics
  const latencyStats = useMemo(() => {
    if (metrics.length === 0) return null

    const latencies = metrics
      .filter(m => m.success)
      .map(m => m.totalLatency)
      .sort((a, b) => a - b)

    if (latencies.length === 0) return null

    const sum = latencies.reduce((acc, val) => acc + val, 0)
    const average = sum / latencies.length
    const median = latencies[Math.floor(latencies.length / 2)]
    const p95Index = Math.floor(latencies.length * 0.95)
    const p99Index = Math.floor(latencies.length * 0.99)
    
    const variance = latencies.reduce((acc, val) => acc + Math.pow(val - average, 2), 0) / latencies.length
    const standardDeviation = Math.sqrt(variance)

    const errorRate = (metrics.filter(m => !m.success).length / metrics.length) * 100

    return {
      average,
      median,
      p95: latencies[p95Index] || 0,
      p99: latencies[p99Index] || 0,
      min: latencies[0] || 0,
      max: latencies[latencies.length - 1] || 0,
      standardDeviation,
      errorRate,
      throughput: metrics.length / ((Date.now() - metrics[0]?.timestamp.getTime()) / 1000) || 0
    }
  }, [metrics])

  // Process chart data
  const chartData = useMemo(() => {
    const now = Date.now()
    const timeRangeMs = {
      '1m': 60 * 1000,
      '5m': 5 * 60 * 1000,
      '15m': 15 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '24h': 24 * 60 * 60 * 1000
    }[timeRange]

    const filteredMetrics = [...metrics, ...realTimeMetrics]
      .filter(m => now - m.timestamp.getTime() <= timeRangeMs)
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())

    return filteredMetrics.map(metric => ({
      time: metric.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      timestamp: metric.timestamp.getTime(),
      latency: metric.totalLatency,
      network: metric.breakdown.networkLatency,
      server: metric.breakdown.serverProcessing,
      audio: metric.breakdown.audioProcessing,
      ai: metric.breakdown.aiInference,
      response: metric.breakdown.responseGeneration,
      success: metric.success
    }))
  }, [metrics, realTimeMetrics, timeRange])

  // Breakdown chart data
  const breakdownData = useMemo(() => {
    if (metrics.length === 0) return []

    const successful = metrics.filter(m => m.success)
    if (successful.length === 0) return []

    const avgBreakdown = {
      networkLatency: 0,
      serverProcessing: 0,
      audioProcessing: 0,
      aiInference: 0,
      responseGeneration: 0
    }

    successful.forEach(metric => {
      Object.keys(avgBreakdown).forEach(key => {
        avgBreakdown[key as keyof typeof avgBreakdown] += metric.breakdown[key as keyof typeof metric.breakdown]
      })
    })

    Object.keys(avgBreakdown).forEach(key => {
      avgBreakdown[key as keyof typeof avgBreakdown] /= successful.length
    })

    return [
      { name: 'Network', value: Math.round(avgBreakdown.networkLatency), color: '#3b82f6' },
      { name: 'Server', value: Math.round(avgBreakdown.serverProcessing), color: '#22c55e' },
      { name: 'Audio', value: Math.round(avgBreakdown.audioProcessing), color: '#f59e0b' },
      { name: 'AI Inference', value: Math.round(avgBreakdown.aiInference), color: '#ef4444' },
      { name: 'Response', value: Math.round(avgBreakdown.responseGeneration), color: '#8b5cf6' }
    ]
  }, [metrics])

  const runSingleTest = async (testId: string) => {
    if (!onTestRun) return

    const test = tests.find(t => t.id === testId)
    if (!test) return

    setIsRunning(true)
    setCurrentTest(testId)
    setCurrentIteration(0)
    setTotalIterations(test.iterations)
    setProgress(0)

    try {
      const results = await onTestRun(testId)
      setMetrics(prev => [...prev, ...results])
      setProgress(100)
    } catch (error) {
      console.error('Test failed:', error)
    } finally {
      setIsRunning(false)
      setCurrentTest(null)
    }
  }

  const runSelectedTests = async () => {
    if (!onBulkTest || selectedTests.length === 0) return

    setIsRunning(true)
    setProgress(0)

    const totalTests = selectedTests.reduce((sum, testId) => {
      const test = tests.find(t => t.id === testId)
      return sum + (test?.iterations || 0)
    }, 0)

    setTotalIterations(totalTests)

    try {
      const results = await onBulkTest(selectedTests)
      setMetrics(prev => [...prev, ...results])
      setProgress(100)
    } catch (error) {
      console.error('Bulk test failed:', error)
    } finally {
      setIsRunning(false)
    }
  }

  const stopTests = () => {
    setIsRunning(false)
    setCurrentTest(null)
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }
  }

  const clearMetrics = () => {
    setMetrics([])
    setProgress(0)
    setCurrentIteration(0)
    setTotalIterations(0)
  }

  const toggleTestSelection = (testId: string) => {
    setSelectedTests(prev =>
      prev.includes(testId)
        ? prev.filter(id => id !== testId)
        : [...prev, testId]
    )
  }

  const getLatencyColor = (latency: number) => {
    if (latency < 500) return 'text-green-600'
    if (latency < 1000) return 'text-yellow-600'
    if (latency < 2000) return 'text-orange-600'
    return 'text-red-600'
  }

  const getStatusIcon = (test: LatencyTest) => {
    if (!test.enabled) return <Monitor size={16} className="text-gray-400" />
    if (currentTest === test.id) return <Activity size={16} className="text-blue-500 animate-pulse" />
    return <CheckCircle size={16} className="text-green-500" />
  }

  // Auto-refresh for real-time mode
  useEffect(() => {
    if (autoRefresh && viewMode === 'realtime') {
      intervalRef.current = setInterval(() => {
        // Trigger refresh - would typically call an API
      }, 1000)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [autoRefresh, viewMode])

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <Activity size={20} className="text-primary" />
            <span>Latency Profiler</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Monitor and analyze system latency across different endpoints
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button size="sm" variant="outline" onClick={() => setShowTestConfig('new')}>
            <Settings size={14} className="mr-1" />
            Configure
          </Button>
          <Button size="sm" variant="outline" onClick={clearMetrics}>
            <RotateCcw size={14} className="mr-1" />
            Clear
          </Button>
          <Button size="sm" variant="outline">
            <Download size={14} className="mr-1" />
            Export
          </Button>
        </div>
      </div>

      {/* View Mode Selector */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-1 bg-muted rounded-lg p-1">
          {[
            { id: 'overview', label: 'Overview', icon: Monitor },
            { id: 'breakdown', label: 'Breakdown', icon: BarChart },
            { id: 'comparison', label: 'Comparison', icon: TrendingUp },
            { id: 'realtime', label: 'Real-time', icon: Activity }
          ].map((mode) => {
            const Icon = mode.icon
            return (
              <button
                key={mode.id}
                onClick={() => setViewMode(mode.id as any)}
                className={cn(
                  "flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  viewMode === mode.id ? "bg-background shadow-sm" : "hover:bg-background/50"
                )}
              >
                <Icon size={14} />
                <span>{mode.label}</span>
              </button>
            )
          })}
        </div>

        <div className="flex items-center space-x-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded bg-background"
          >
            <option value="1m">Last 1 minute</option>
            <option value="5m">Last 5 minutes</option>
            <option value="15m">Last 15 minutes</option>
            <option value="1h">Last 1 hour</option>
            <option value="24h">Last 24 hours</option>
          </select>
        </div>
      </div>

      {/* Statistics Dashboard */}
      {latencyStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className={cn("text-2xl font-bold", getLatencyColor(latencyStats.average))}>
              {Math.round(latencyStats.average)}ms
            </div>
            <div className="text-sm text-muted-foreground">Average</div>
          </div>
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className={cn("text-2xl font-bold", getLatencyColor(latencyStats.median))}>
              {Math.round(latencyStats.median)}ms
            </div>
            <div className="text-sm text-muted-foreground">Median</div>
          </div>
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className={cn("text-2xl font-bold", getLatencyColor(latencyStats.p95))}>
              {Math.round(latencyStats.p95)}ms
            </div>
            <div className="text-sm text-muted-foreground">95th Percentile</div>
          </div>
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className={cn("text-2xl font-bold", getLatencyColor(latencyStats.p99))}>
              {Math.round(latencyStats.p99)}ms
            </div>
            <div className="text-sm text-muted-foreground">99th Percentile</div>
          </div>
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className={cn(
              "text-2xl font-bold",
              latencyStats.errorRate > alertThresholds.errorRate ? "text-red-600" : "text-green-600"
            )}>
              {latencyStats.errorRate.toFixed(1)}%
            </div>
            <div className="text-sm text-muted-foreground">Error Rate</div>
          </div>
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className="text-2xl font-bold">
              {latencyStats.throughput.toFixed(1)}
            </div>
            <div className="text-sm text-muted-foreground">RPS</div>
          </div>
        </div>
      )}

      {/* Alert Indicators */}
      {latencyStats && (
        <div className="space-y-2">
          {latencyStats.average > alertThresholds.latency && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-900/10 dark:border-red-800">
              <AlertTriangle size={16} className="text-red-600" />
              <span className="text-sm text-red-800 dark:text-red-200">
                Average latency ({Math.round(latencyStats.average)}ms) exceeds threshold ({alertThresholds.latency}ms)
              </span>
            </div>
          )}
          {latencyStats.errorRate > alertThresholds.errorRate && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-900/10 dark:border-red-800">
              <AlertTriangle size={16} className="text-red-600" />
              <span className="text-sm text-red-800 dark:text-red-200">
                Error rate ({latencyStats.errorRate.toFixed(1)}%) exceeds threshold ({alertThresholds.errorRate}%)
              </span>
            </div>
          )}
          {latencyStats.p95 > alertThresholds.p95 && (
            <div className="flex items-center space-x-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg dark:bg-yellow-900/10 dark:border-yellow-800">
              <AlertTriangle size={16} className="text-yellow-600" />
              <span className="text-sm text-yellow-800 dark:text-yellow-200">
                95th percentile ({Math.round(latencyStats.p95)}ms) exceeds threshold ({alertThresholds.p95}ms)
              </span>
            </div>
          )}
        </div>
      )}

      {/* Test Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Test List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Tests ({selectedTests.length} selected)</h4>
            <div className="flex space-x-2">
              <Button
                size="sm"
                onClick={runSelectedTests}
                disabled={isRunning || selectedTests.length === 0}
              >
                {isRunning ? (
                  <Activity size={14} className="animate-spin" />
                ) : (
                  <Play size={14} />
                )}
              </Button>
              {isRunning && (
                <Button size="sm" variant="outline" onClick={stopTests}>
                  <Square size={14} />
                </Button>
              )}
            </div>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {tests.map(test => (
              <div
                key={test.id}
                className={cn(
                  "p-3 border rounded-lg transition-colors",
                  selectedTests.includes(test.id) ? "border-primary bg-primary/5" : "hover:bg-muted/50",
                  !test.enabled && "opacity-50"
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <input
                        type="checkbox"
                        checked={selectedTests.includes(test.id)}
                        onChange={() => toggleTestSelection(test.id)}
                        className="rounded"
                        disabled={!test.enabled}
                      />
                      <h5 className="font-medium">{test.name}</h5>
                      {getStatusIcon(test)}
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{test.description}</p>
                    <div className="text-xs text-muted-foreground">
                      {test.endpoint} • {test.iterations} iterations • {test.expectedLatency}ms expected
                    </div>
                  </div>
                  
                  <div className="flex space-x-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => runSingleTest(test.id)}
                      disabled={isRunning || !test.enabled}
                    >
                      <Play size={12} />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowTestConfig(test.id)}
                    >
                      <Settings size={12} />
                    </Button>
                  </div>
                </div>

                {/* Progress for current test */}
                {currentTest === test.id && (
                  <div className="mt-3">
                    <div className="w-full bg-muted rounded-full h-2">
                      <div 
                        className="h-2 bg-primary rounded-full transition-all"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {currentIteration} / {totalIterations} iterations
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Main Chart */}
        <div className="lg:col-span-2 space-y-4">
          {viewMode === 'overview' && (
            <div>
              <h4 className="font-medium mb-3">Latency Over Time</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Line 
                      type="monotone" 
                      dataKey="latency" 
                      stroke="#3b82f6" 
                      strokeWidth={2}
                      dot={{ r: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {viewMode === 'breakdown' && (
            <div>
              <h4 className="font-medium mb-3">Latency Breakdown</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={breakdownData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {viewMode === 'comparison' && (
            <div>
              <h4 className="font-medium mb-3">Component Comparison</h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="network"
                      stackId="1"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.8}
                    />
                    <Area
                      type="monotone"
                      dataKey="server"
                      stackId="1"
                      stroke="#22c55e"
                      fill="#22c55e"
                      fillOpacity={0.8}
                    />
                    <Area
                      type="monotone"
                      dataKey="ai"
                      stackId="1"
                      stroke="#ef4444"
                      fill="#ef4444"
                      fillOpacity={0.8}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {viewMode === 'realtime' && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium">Real-time Monitoring</h4>
                <div className="flex items-center space-x-2">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    autoRefresh ? "bg-green-500 animate-pulse" : "bg-gray-400"
                  )} />
                  <span className="text-sm text-muted-foreground">
                    {autoRefresh ? 'Live' : 'Paused'}
                  </span>
                </div>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData.slice(-20)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Line 
                      type="monotone" 
                      dataKey="latency" 
                      stroke="#3b82f6" 
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive={true}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Component Breakdown */}
          {breakdownData.length > 0 && viewMode !== 'breakdown' && (
            <div>
              <h4 className="font-medium mb-3">Average Component Latency</h4>
              <div className="grid grid-cols-5 gap-3">
                {breakdownData.map((item, index) => (
                  <div key={index} className="p-3 bg-card border rounded-lg text-center">
                    <div className="text-lg font-bold" style={{ color: item.color }}>
                      {item.value}ms
                    </div>
                    <div className="text-xs text-muted-foreground">{item.name}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recent Metrics Table */}
      {metrics.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium">Recent Results</h4>
          <div className="overflow-x-auto">
            <table className="w-full border rounded-lg">
              <thead className="bg-muted/50">
                <tr>
                  <th className="p-3 text-left font-medium">Timestamp</th>
                  <th className="p-3 text-center font-medium">Endpoint</th>
                  <th className="p-3 text-center font-medium">Total Latency</th>
                  <th className="p-3 text-center font-medium">Network</th>
                  <th className="p-3 text-center font-medium">AI Inference</th>
                  <th className="p-3 text-center font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {metrics.slice(-10).reverse().map((metric, index) => (
                  <tr key={index} className="border-t">
                    <td className="p-3 text-sm">
                      {metric.timestamp.toLocaleTimeString()}
                    </td>
                    <td className="p-3 text-center text-sm font-medium">
                      {metric.endpoint}
                    </td>
                    <td className="p-3 text-center">
                      <span className={cn("font-medium", getLatencyColor(metric.totalLatency))}>
                        {Math.round(metric.totalLatency)}ms
                      </span>
                    </td>
                    <td className="p-3 text-center text-sm">
                      {Math.round(metric.breakdown.networkLatency)}ms
                    </td>
                    <td className="p-3 text-center text-sm">
                      {Math.round(metric.breakdown.aiInference)}ms
                    </td>
                    <td className="p-3 text-center">
                      {metric.success ? (
                        <CheckCircle size={16} className="text-green-500 mx-auto" />
                      ) : (
                        <AlertTriangle size={16} className="text-red-500 mx-auto" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {metrics.length === 0 && !isRunning && (
        <div className="p-8 text-center text-muted-foreground">
          <Clock size={48} className="mx-auto mb-4 opacity-50" />
          <h4 className="font-medium mb-2">No Latency Data</h4>
          <p className="text-sm">
            Run some tests to see latency metrics and analysis
          </p>
        </div>
      )}
    </div>
  )
}