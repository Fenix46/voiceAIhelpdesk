import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { TicketSummary } from '@/components/TicketSummary'
import { 
  Search,
  Filter,
  Plus,
  FileText,
  Clock,
  User,
  AlertCircle,
  CheckCircle,
  Trash2,
  Edit,
  Download,
  Calendar
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { format } from 'date-fns'

interface Ticket {
  id: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  status: 'open' | 'in-progress' | 'resolved' | 'closed'
  category: string
  customerInfo: {
    name: string
    email: string
    phone?: string
  }
  estimatedResolution: string
  tags: string[]
  createdAt: Date
  updatedAt: Date
  assignedTo?: string
}

export function TicketsPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [showCreateTicket, setShowCreateTicket] = useState(false)

  const { data: tickets, isLoading } = useQuery({
    queryKey: ['tickets', searchTerm, statusFilter, priorityFilter],
    queryFn: async () => {
      // Simulate API call - replace with actual API endpoint
      await new Promise(resolve => setTimeout(resolve, 500))
      
      // Mock data
      const mockTickets: Ticket[] = [
        {
          id: 'TKT-001',
          title: 'Audio quality issues during recording',
          description: 'Customer reports poor audio quality when using the voice recorder. Background noise is not being filtered properly.',
          priority: 'high',
          status: 'open',
          category: 'Technical',
          customerInfo: {
            name: 'John Smith',
            email: 'john.smith@example.com',
            phone: '+1-555-0123'
          },
          estimatedResolution: '4 hours',
          tags: ['audio', 'quality', 'recording'],
          createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
          updatedAt: new Date(Date.now() - 30 * 60 * 1000), // 30 minutes ago
          assignedTo: 'Tech Support Team'
        },
        {
          id: 'TKT-002',
          title: 'Cannot generate support ticket',
          description: 'User is unable to create a support ticket from their conversation. The button appears disabled.',
          priority: 'medium',
          status: 'in-progress',
          category: 'Bug',
          customerInfo: {
            name: 'Sarah Johnson',
            email: 'sarah.j@company.com'
          },
          estimatedResolution: '2 hours',
          tags: ['ticket', 'generation', 'ui'],
          createdAt: new Date(Date.now() - 4 * 60 * 60 * 1000), // 4 hours ago
          updatedAt: new Date(Date.now() - 15 * 60 * 1000), // 15 minutes ago
          assignedTo: 'Development Team'
        },
        {
          id: 'TKT-003',
          title: 'Feature request: Dark mode toggle',
          description: 'Customer requests a dark mode option for better usability during night hours.',
          priority: 'low',
          status: 'resolved',
          category: 'Feature Request',
          customerInfo: {
            name: 'Mike Davis',
            email: 'mike.davis@email.com'
          },
          estimatedResolution: 'Next Release',
          tags: ['dark-mode', 'ui', 'enhancement'],
          createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000), // 1 day ago
          updatedAt: new Date(Date.now() - 60 * 60 * 1000), // 1 hour ago
        },
        {
          id: 'TKT-004',
          title: 'Connection timeout during long sessions',
          description: 'WebSocket connection drops after 10 minutes of continuous conversation.',
          priority: 'urgent',
          status: 'open',
          category: 'Technical',
          customerInfo: {
            name: 'Lisa Chen',
            email: 'lisa.chen@corp.com'
          },
          estimatedResolution: '1 hour',
          tags: ['websocket', 'timeout', 'connection'],
          createdAt: new Date(Date.now() - 30 * 60 * 1000), // 30 minutes ago
          updatedAt: new Date(Date.now() - 30 * 60 * 1000),
          assignedTo: 'DevOps Team'
        }
      ]

      // Apply filters
      return mockTickets.filter(ticket => {
        const matchesSearch = searchTerm === '' || 
          ticket.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
          ticket.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
          ticket.customerInfo.name.toLowerCase().includes(searchTerm.toLowerCase())
        
        const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter
        const matchesPriority = priorityFilter === 'all' || ticket.priority === priorityFilter
        
        return matchesSearch && matchesStatus && matchesPriority
      })
    }
  })

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/20'
      case 'high': return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/20'
      case 'medium': return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/20'
      case 'low': return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/20'
      default: return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'open': return 'text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-900/20'
      case 'in-progress': return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/20'
      case 'resolved': return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/20'
      case 'closed': return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20'
      default: return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'open': return AlertCircle
      case 'in-progress': return Clock
      case 'resolved': return CheckCircle
      case 'closed': return CheckCircle
      default: return FileText
    }
  }

  if (selectedTicket || showCreateTicket) {
    return (
      <div className="max-w-4xl mx-auto">
        <TicketSummary
          ticket={selectedTicket || undefined}
          onSave={(ticket) => {
            console.log('Ticket saved:', ticket)
            setSelectedTicket(null)
            setShowCreateTicket(false)
          }}
          onClose={() => {
            setSelectedTicket(null)
            setShowCreateTicket(false)
          }}
        />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">Support Tickets</h1>
          <p className="text-muted-foreground">
            Manage and track customer support requests
          </p>
        </div>
        
        <Button onClick={() => setShowCreateTicket(true)}>
          <Plus size={16} className="mr-2" />
          New Ticket
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-card border rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search tickets by ID, title, or customer..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-md bg-background"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border rounded-md bg-background"
          >
            <option value="all">All Status</option>
            <option value="open">Open</option>
            <option value="in-progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>

          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-3 py-2 border rounded-md bg-background"
          >
            <option value="all">All Priority</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Tickets List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-card border rounded-lg p-6 animate-pulse">
                <div className="h-4 bg-muted rounded w-1/3 mb-4"></div>
                <div className="h-3 bg-muted rounded w-full mb-2"></div>
                <div className="h-3 bg-muted rounded w-2/3"></div>
              </div>
            ))}
          </div>
        ) : tickets?.length === 0 ? (
          <div className="text-center py-12">
            <FileText size={48} className="mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No tickets found</h3>
            <p className="text-muted-foreground mb-4">
              {searchTerm || statusFilter !== 'all' || priorityFilter !== 'all'
                ? 'Try adjusting your filters to see more results.'
                : 'Create your first support ticket to get started.'
              }
            </p>
            <Button onClick={() => setShowCreateTicket(true)}>
              <Plus size={16} className="mr-2" />
              Create New Ticket
            </Button>
          </div>
        ) : (
          tickets?.map((ticket) => {
            const StatusIcon = getStatusIcon(ticket.status)
            
            return (
              <div
                key={ticket.id}
                className="bg-card border rounded-lg p-6 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => setSelectedTicket(ticket)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className={cn(
                      "p-2 rounded-full",
                      ticket.priority === 'urgent' ? 'bg-red-100 dark:bg-red-900/20' :
                      ticket.priority === 'high' ? 'bg-orange-100 dark:bg-orange-900/20' :
                      'bg-muted'
                    )}>
                      <StatusIcon size={16} className={
                        ticket.priority === 'urgent' ? 'text-red-600 dark:text-red-400' :
                        ticket.priority === 'high' ? 'text-orange-600 dark:text-orange-400' :
                        'text-muted-foreground'
                      } />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">{ticket.title}</h3>
                      <p className="text-sm text-muted-foreground">#{ticket.id}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <span className={cn(
                      "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium",
                      getPriorityColor(ticket.priority)
                    )}>
                      {ticket.priority}
                    </span>
                    <span className={cn(
                      "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium",
                      getStatusColor(ticket.status)
                    )}>
                      {ticket.status.replace('-', ' ')}
                    </span>
                  </div>
                </div>

                <p className="text-muted-foreground mb-4 line-clamp-2">
                  {ticket.description}
                </p>

                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center space-x-4">
                    <div className="flex items-center space-x-1">
                      <User size={14} />
                      <span>{ticket.customerInfo.name}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Calendar size={14} />
                      <span>{format(ticket.createdAt, 'MMM d, HH:mm')}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Clock size={14} />
                      <span>ETA: {ticket.estimatedResolution}</span>
                    </div>
                  </div>
                  
                  {ticket.assignedTo && (
                    <span className="text-muted-foreground">
                      Assigned to: {ticket.assignedTo}
                    </span>
                  )}
                </div>

                {ticket.tags.length > 0 && (
                  <div className="flex items-center space-x-2 mt-3">
                    {ticket.tags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center px-2 py-1 rounded-md text-xs bg-muted text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Summary Stats */}
      {tickets && tickets.length > 0 && (
        <div className="bg-card border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Summary</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-600">
                {tickets.filter(t => t.status === 'open').length}
              </div>
              <div className="text-sm text-muted-foreground">Open</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-600">
                {tickets.filter(t => t.status === 'in-progress').length}
              </div>
              <div className="text-sm text-muted-foreground">In Progress</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-green-600">
                {tickets.filter(t => t.status === 'resolved').length}
              </div>
              <div className="text-sm text-muted-foreground">Resolved</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-red-600">
                {tickets.filter(t => t.priority === 'urgent').length}
              </div>
              <div className="text-sm text-muted-foreground">Urgent</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}