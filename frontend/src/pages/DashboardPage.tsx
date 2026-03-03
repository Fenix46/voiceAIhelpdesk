import { MetricsDashboard } from '@/components/MetricsDashboard'
import { Button } from '@/components/ui/button'
import { useNavigate } from 'react-router-dom'
import { 
  RefreshCw,
  Download,
  Calendar,
  TrendingUp,
  AlertCircle,
  MessageSquare
} from 'lucide-react'

export function DashboardPage() {
  const navigate = useNavigate()

  const handleExportMetrics = () => {
    // This would typically make an API call to get metrics data
    const metricsData = {
      exportedAt: new Date().toISOString(),
      timeRange: '24h',
      systemHealth: 'good',
      metrics: {
        totalSessions: 847,
        avgSessionDuration: 245,
        totalTickets: 156,
        resolvedTickets: 132,
        customerSatisfaction: 94.2
      }
    }
    
    const blob = new Blob([JSON.stringify(metricsData, null, 2)], {
      type: 'application/json'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `metrics-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleRefresh = () => {
    window.location.reload()
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
          <p className="text-muted-foreground">
            Monitor system performance and user engagement in real-time
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
          >
            <RefreshCw size={16} className="mr-2" />
            Refresh
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportMetrics}
          >
            <Download size={16} className="mr-2" />
            Export
          </Button>
          
          <Button
            size="sm"
            onClick={() => navigate('/conversation')}
          >
            <MessageSquare size={16} className="mr-2" />
            New Conversation
          </Button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Button
          variant="outline"
          className="h-auto p-4 justify-start"
          onClick={() => navigate('/conversation')}
        >
          <div className="flex items-center space-x-3">
            <MessageSquare size={20} className="text-primary" />
            <div className="text-left">
              <div className="font-medium">Start Session</div>
              <div className="text-xs text-muted-foreground">Begin new conversation</div>
            </div>
          </div>
        </Button>
        
        <Button
          variant="outline"
          className="h-auto p-4 justify-start"
          onClick={() => navigate('/tickets')}
        >
          <div className="flex items-center space-x-3">
            <Calendar size={20} className="text-primary" />
            <div className="text-left">
              <div className="font-medium">View Tickets</div>
              <div className="text-xs text-muted-foreground">Manage support tickets</div>
            </div>
          </div>
        </Button>
        
        <Button
          variant="outline"
          className="h-auto p-4 justify-start"
          onClick={() => navigate('/settings')}
        >
          <div className="flex items-center space-x-3">
            <TrendingUp size={20} className="text-primary" />
            <div className="text-left">
              <div className="font-medium">Settings</div>
              <div className="text-xs text-muted-foreground">Configure system</div>
            </div>
          </div>
        </Button>
        
        <Button
          variant="outline"
          className="h-auto p-4 justify-start"
          onClick={handleExportMetrics}
        >
          <div className="flex items-center space-x-3">
            <Download size={20} className="text-primary" />
            <div className="text-left">
              <div className="font-medium">Export Data</div>
              <div className="text-xs text-muted-foreground">Download metrics</div>
            </div>
          </div>
        </Button>
      </div>

      {/* System Alerts */}
      <div className="bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
        <div className="flex items-center space-x-2">
          <AlertCircle size={16} className="text-yellow-600 dark:text-yellow-400" />
          <span className="font-medium text-yellow-800 dark:text-yellow-200">System Notice</span>
        </div>
        <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
          Scheduled maintenance is planned for this weekend. All services will remain operational.
        </p>
      </div>

      {/* Main Dashboard */}
      <MetricsDashboard />

      {/* Additional Information */}
      <div className="bg-muted/50 rounded-lg p-6">
        <h2 className="font-semibold mb-4">About This Dashboard</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm">
          <div>
            <h3 className="font-medium mb-2">Real-Time Updates</h3>
            <p className="text-muted-foreground">
              All metrics are updated every 30 seconds to provide real-time insights 
              into system performance and user activity.
            </p>
          </div>
          <div>
            <h3 className="font-medium mb-2">Data Retention</h3>
            <p className="text-muted-foreground">
              Detailed metrics are retained for 90 days. Historical data beyond this 
              period is aggregated for long-term trend analysis.
            </p>
          </div>
          <div>
            <h3 className="font-medium mb-2">Privacy & Security</h3>
            <p className="text-muted-foreground">
              All data is encrypted in transit and at rest. Personal information is 
              anonymized in analytics to protect user privacy.
            </p>
          </div>
          <div>
            <h3 className="font-medium mb-2">System Requirements</h3>
            <p className="text-muted-foreground">
              Best viewed in modern browsers with JavaScript enabled. 
              Mobile-optimized interface available for all screen sizes.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}