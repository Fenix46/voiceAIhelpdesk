import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useConversationStore } from '@/store/conversationStore'
import { useAppStore } from '@/store/appStore'
import { 
  FileText, 
  Download, 
  Share, 
  Edit,
  Save,
  X,
  User,
  Clock,
  Tag,
  AlertCircle
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface TicketData {
  id: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  category: string
  customerInfo: {
    name: string
    email: string
    phone?: string
  }
  estimatedResolution: string
  tags: string[]
  createdAt: Date
}

interface TicketSummaryProps {
  ticket?: TicketData
  onSave?: (ticket: TicketData) => void
  onClose?: () => void
}

export function TicketSummary({ ticket: initialTicket, onSave, onClose }: TicketSummaryProps) {
  const { messages } = useConversationStore()
  const { addNotification } = useAppStore()
  const [isEditing, setIsEditing] = useState(!initialTicket)
  const [ticket, setTicket] = useState<TicketData>(initialTicket || {
    id: crypto.randomUUID(),
    title: 'New Support Ticket',
    description: '',
    priority: 'medium',
    category: 'General',
    customerInfo: {
      name: '',
      email: '',
    },
    estimatedResolution: '24 hours',
    tags: [],
    createdAt: new Date(),
  })

  const generateSummary = () => {
    const userMessages = messages.filter(m => m.role === 'user')
    const assistantMessages = messages.filter(m => m.role === 'assistant')
    
    const summary = `
Customer Issue Summary:
${userMessages.map(m => `- ${m.content}`).join('\n')}

System Responses:
${assistantMessages.map(m => `- ${m.content}`).join('\n')}

Conversation Length: ${messages.length} messages
Session Duration: ${new Date().toLocaleTimeString()}
    `.trim()

    setTicket(prev => ({ ...prev, description: summary }))
  }

  const handleSave = () => {
    onSave?.(ticket)
    setIsEditing(false)
    addNotification({
      type: 'success',
      message: 'Ticket saved successfully'
    })
  }

  const handleExport = () => {
    const exportData = {
      ...ticket,
      conversation: messages,
      exportedAt: new Date().toISOString()
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ticket-${ticket.id}.json`
    a.click()
    URL.revokeObjectURL(url)
    
    addNotification({
      type: 'success',
      message: 'Ticket exported successfully'
    })
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/20'
      case 'high': return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/20'
      case 'medium': return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/20'
      case 'low': return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/20'
      default: return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20'
    }
  }

  return (
    <div className="bg-card border rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <FileText size={20} className="text-primary" />
          <h2 className="text-lg font-semibold">Ticket Summary</h2>
        </div>
        <div className="flex items-center space-x-2">
          {!isEditing && (
            <>
              <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)}>
                <Edit size={16} />
              </Button>
              <Button variant="ghost" size="sm" onClick={handleExport}>
                <Download size={16} />
              </Button>
            </>
          )}
          {onClose && (
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X size={16} />
            </Button>
          )}
        </div>
      </div>

      {/* Ticket Info */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium text-muted-foreground">Ticket ID</label>
          <p className="font-mono text-sm">{ticket.id}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">Created</label>
          <p className="text-sm">{ticket.createdAt.toLocaleString()}</p>
        </div>
      </div>

      {/* Title */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">Title</label>
        {isEditing ? (
          <input
            type="text"
            value={ticket.title}
            onChange={(e) => setTicket(prev => ({ ...prev, title: e.target.value }))}
            className="w-full mt-1 px-3 py-2 border rounded-md bg-background"
          />
        ) : (
          <h3 className="text-lg font-medium mt-1">{ticket.title}</h3>
        )}
      </div>

      {/* Priority and Category */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-medium text-muted-foreground">Priority</label>
          {isEditing ? (
            <select
              value={ticket.priority}
              onChange={(e) => setTicket(prev => ({ ...prev, priority: e.target.value as any }))}
              className="w-full mt-1 px-3 py-2 border rounded-md bg-background"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          ) : (
            <span className={cn(
              "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium mt-1",
              getPriorityColor(ticket.priority)
            )}>
              <AlertCircle size={12} className="mr-1" />
              {ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}
            </span>
          )}
        </div>
        <div>
          <label className="text-sm font-medium text-muted-foreground">Category</label>
          {isEditing ? (
            <input
              type="text"
              value={ticket.category}
              onChange={(e) => setTicket(prev => ({ ...prev, category: e.target.value }))}
              className="w-full mt-1 px-3 py-2 border rounded-md bg-background"
            />
          ) : (
            <div className="flex items-center mt-1">
              <Tag size={14} className="mr-1" />
              <span>{ticket.category}</span>
            </div>
          )}
        </div>
      </div>

      {/* Customer Info */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">Customer Information</label>
        <div className="mt-2 p-3 bg-muted rounded-md space-y-2">
          {isEditing ? (
            <>
              <input
                type="text"
                placeholder="Customer Name"
                value={ticket.customerInfo.name}
                onChange={(e) => setTicket(prev => ({ 
                  ...prev, 
                  customerInfo: { ...prev.customerInfo, name: e.target.value }
                }))}
                className="w-full px-3 py-2 border rounded-md bg-background"
              />
              <input
                type="email"
                placeholder="Customer Email"
                value={ticket.customerInfo.email}
                onChange={(e) => setTicket(prev => ({ 
                  ...prev, 
                  customerInfo: { ...prev.customerInfo, email: e.target.value }
                }))}
                className="w-full px-3 py-2 border rounded-md bg-background"
              />
            </>
          ) : (
            <div className="flex items-center space-x-2">
              <User size={16} />
              <div>
                <p className="font-medium">{ticket.customerInfo.name || 'Unknown'}</p>
                <p className="text-sm text-muted-foreground">{ticket.customerInfo.email}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Description */}
      <div>
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-muted-foreground">Description</label>
          {!ticket.description && (
            <Button
              variant="ghost"
              size="sm"
              onClick={generateSummary}
              className="text-primary"
            >
              Generate from conversation
            </Button>
          )}
        </div>
        {isEditing ? (
          <textarea
            value={ticket.description}
            onChange={(e) => setTicket(prev => ({ ...prev, description: e.target.value }))}
            className="w-full mt-1 px-3 py-2 border rounded-md bg-background h-32 resize-none"
            placeholder="Describe the issue and any relevant details..."
          />
        ) : (
          <div className="mt-1 p-3 bg-muted rounded-md whitespace-pre-wrap text-sm">
            {ticket.description || 'No description available'}
          </div>
        )}
      </div>

      {/* Estimated Resolution */}
      <div>
        <label className="text-sm font-medium text-muted-foreground">Estimated Resolution</label>
        {isEditing ? (
          <input
            type="text"
            value={ticket.estimatedResolution}
            onChange={(e) => setTicket(prev => ({ ...prev, estimatedResolution: e.target.value }))}
            className="w-full mt-1 px-3 py-2 border rounded-md bg-background"
          />
        ) : (
          <div className="flex items-center mt-1">
            <Clock size={14} className="mr-1" />
            <span>{ticket.estimatedResolution}</span>
          </div>
        )}
      </div>

      {/* Actions */}
      {isEditing && (
        <div className="flex items-center justify-end space-x-2 pt-4 border-t">
          <Button variant="ghost" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save size={16} className="mr-2" />
            Save Ticket
          </Button>
        </div>
      )}
    </div>
  )
}