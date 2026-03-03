import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  BarChart3,
  TrendingUp,
  Clock,
  Users,
  Headphones,
  CheckCircle,
  AlertTriangle,
  Activity
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface MetricsData {
  totalSessions: number
  avgSessionDuration: number
  totalTickets: number
  resolvedTickets: number
  avgResolutionTime: string
  customerSatisfaction: number
  activeUsers: number
  systemUptime: number
}

interface MetricCardProps {
  title: string
  value: string | number
  change?: number
  icon: React.ComponentType<any>
  color?: string
}

function MetricCard({ title, value, change, icon: Icon, color = "text-primary" }: MetricCardProps) {
  return (
    <div className="bg-card border rounded-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-2">{value}</p>
          {change !== undefined && (
            <div className={cn(
              "flex items-center mt-1 text-sm",
              change >= 0 ? "text-green-600" : "text-red-600"
            )}>
              <TrendingUp size={14} className="mr-1" />
              <span>{change >= 0 ? '+' : ''}{change}%</span>
            </div>
          )}
        </div>
        <div className={cn("p-3 rounded-full bg-muted", color)}>
          <Icon size={24} />
        </div>
      </div>
    </div>
  )
}

export function MetricsDashboard() {
  const [timeRange, setTimeRange] = useState<'1h' | '24h' | '7d' | '30d'>('24h')
  
  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['metrics', timeRange],
    queryFn: async () => {
      // Simulate API call - replace with actual API endpoint
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      const mockData: MetricsData = {
        totalSessions: Math.floor(Math.random() * 1000) + 500,
        avgSessionDuration: Math.floor(Math.random() * 300) + 180, // seconds
        totalTickets: Math.floor(Math.random() * 200) + 100,
        resolvedTickets: Math.floor(Math.random() * 150) + 80,
        avgResolutionTime: `${Math.floor(Math.random() * 4) + 1}h ${Math.floor(Math.random() * 60)}m`,
        customerSatisfaction: Math.random() * 20 + 80, // 80-100%
        activeUsers: Math.floor(Math.random() * 50) + 10,
        systemUptime: Math.random() * 5 + 95, // 95-100%
      }
      
      return mockData
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  }

  const resolutionRate = metrics 
    ? Math.round((metrics.resolvedTickets / metrics.totalTickets) * 100)
    : 0

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold">Live Metrics</h2>
          <div className="animate-spin h-6 w-6 border border-primary border-t-transparent rounded-full" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="bg-card border rounded-lg p-6 animate-pulse">
              <div className="h-4 bg-muted rounded w-3/4 mb-4"></div>
              <div className="h-8 bg-muted rounded w-1/2"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle size={48} className="mx-auto text-destructive mb-4" />
        <h3 className="text-lg font-medium mb-2">Failed to load metrics</h3>
        <p className="text-muted-foreground">Please check your connection and try again</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Live Metrics</h2>
          <p className="text-muted-foreground">Real-time system performance and usage statistics</p>
        </div>
        
        {/* Time range selector */}
        <div className="flex space-x-1 bg-muted rounded-lg p-1">
          {(['1h', '24h', '7d', '30d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={cn(
                "px-3 py-1 text-sm rounded-md transition-colors",
                timeRange === range
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Sessions"
          value={metrics?.totalSessions.toLocaleString() || '0'}
          change={12}
          icon={Headphones}
          color="text-blue-600"
        />
        
        <MetricCard
          title="Avg Session Duration"
          value={metrics ? formatDuration(metrics.avgSessionDuration) : '0s'}
          change={-5}
          icon={Clock}
          color="text-green-600"
        />
        
        <MetricCard
          title="Active Users"
          value={metrics?.activeUsers || 0}
          change={8}
          icon={Users}
          color="text-purple-600"
        />
        
        <MetricCard
          title="System Uptime"
          value={`${metrics?.systemUptime.toFixed(1) || 0}%`}
          icon={Activity}
          color="text-green-600"
        />
        
        <MetricCard
          title="Total Tickets"
          value={metrics?.totalTickets || 0}
          change={15}
          icon={BarChart3}
          color="text-orange-600"
        />
        
        <MetricCard
          title="Resolution Rate"
          value={`${resolutionRate}%`}
          change={3}
          icon={CheckCircle}
          color="text-green-600"
        />
        
        <MetricCard
          title="Avg Resolution Time"
          value={metrics?.avgResolutionTime || 'N/A'}
          change={-12}
          icon={Clock}
          color="text-blue-600"
        />
        
        <MetricCard
          title="Customer Satisfaction"
          value={`${metrics?.customerSatisfaction.toFixed(1) || 0}%`}
          change={2}
          icon={TrendingUp}
          color="text-green-600"
        />
      </div>

      {/* Status Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">System Status</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">WebSocket Connection</span>
              <div className="flex items-center space-x-2">
                <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-green-600">Connected</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Audio Processing</span>
              <div className="flex items-center space-x-2">
                <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-green-600">Operational</span>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Database</span>
              <div className="flex items-center space-x-2">
                <div className="h-2 w-2 bg-green-500 rounded-full"></div>
                <span className="text-sm text-green-600">Healthy</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Activity</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">New session started</span>
              <span className="text-xs text-muted-foreground">2min ago</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Ticket #1234 resolved</span>
              <span className="text-xs text-muted-foreground">5min ago</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Audio processed</span>
              <span className="text-xs text-muted-foreground">8min ago</span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Performance</h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>CPU Usage</span>
                <span>34%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-blue-600 h-2 rounded-full" style={{ width: '34%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Memory</span>
                <span>67%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-green-600 h-2 rounded-full" style={{ width: '67%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Storage</span>
                <span>23%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-yellow-600 h-2 rounded-full" style={{ width: '23%' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}