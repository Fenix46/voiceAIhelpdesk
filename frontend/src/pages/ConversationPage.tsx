import { useEffect } from 'react'
import { AudioRecorder } from '@/components/AudioRecorder'
import { TranscriptDisplay } from '@/components/TranscriptDisplay'
import { ConversationHistory } from '@/components/ConversationHistory'
import { StatusIndicator } from '@/components/StatusIndicator'
import { TicketSummary } from '@/components/TicketSummary'
import { Button } from '@/components/ui/button'
import { useConversationStore } from '@/store/conversationStore'
import { useAppStore } from '@/store/appStore'
import { socketManager } from '@/lib/socket'
import { 
  FileText, 
  Settings, 
  Download,
  Trash2,
  HelpCircle
} from 'lucide-react'
import { useState } from 'react'

export function ConversationPage() {
  const { messages, sessionId, clearConversation } = useConversationStore()
  const { addNotification } = useAppStore()
  const [showTicketSummary, setShowTicketSummary] = useState(false)

  useEffect(() => {
    // Initialize socket connection when component mounts
    socketManager.connect()
    
    // Set up online/offline listeners
    const handleOnline = () => {
      useAppStore.getState().setOnlineStatus(true)
      addNotification({
        type: 'success',
        message: 'Connection restored'
      })
    }

    const handleOffline = () => {
      useAppStore.getState().setOnlineStatus(false)
      addNotification({
        type: 'warning',
        message: 'You are now offline'
      })
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [addNotification])

  const handleClearConversation = () => {
    if (window.confirm('Are you sure you want to clear the conversation? This action cannot be undone.')) {
      clearConversation()
      addNotification({
        type: 'info',
        message: 'Conversation cleared'
      })
    }
  }

  const handleExportConversation = () => {
    const exportData = {
      sessionId,
      messages,
      exportedAt: new Date().toISOString(),
      messageCount: messages.length
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `conversation-${sessionId || 'unknown'}.json`
    a.click()
    URL.revokeObjectURL(url)
    
    addNotification({
      type: 'success',
      message: 'Conversation exported successfully'
    })
  }

  const hasMessages = messages.length > 0

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">Voice Conversation</h1>
          <div className="flex items-center space-x-4">
            <StatusIndicator />
            {sessionId && (
              <span className="text-sm text-muted-foreground">
                Session: <span className="font-mono">{sessionId.slice(0, 8)}...</span>
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          {hasMessages && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTicketSummary(!showTicketSummary)}
                className="text-primary"
              >
                <FileText size={16} className="mr-2" />
                {showTicketSummary ? 'Hide' : 'Create'} Ticket
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={handleExportConversation}
              >
                <Download size={16} className="mr-2" />
                Export
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearConversation}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 size={16} className="mr-2" />
                Clear
              </Button>
            </>
          )}
          
          <Button
            variant="ghost"
            size="sm"
            onClick={() => window.open('/settings', '_blank')}
          >
            <Settings size={16} />
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-[600px]">
        {/* Left Column - Audio Controls */}
        <div className="lg:col-span-1 space-y-6">
          {/* Audio Recorder */}
          <div className="bg-card border rounded-lg p-6">
            <h2 className="font-semibold mb-4 text-center">Voice Input</h2>
            <AudioRecorder />
          </div>

          {/* Live Transcript */}
          <div className="bg-card border rounded-lg p-6">
            <TranscriptDisplay />
          </div>

          {/* Quick Help */}
          <div className="bg-muted/50 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <HelpCircle size={16} className="text-primary" />
              <span className="font-medium text-sm">Quick Tips</span>
            </div>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>• Click the microphone to start recording</li>
              <li>• Speak clearly for best transcription</li>
              <li>• Use the settings to adjust audio preferences</li>
              <li>• Generate tickets from completed conversations</li>
            </ul>
          </div>
        </div>

        {/* Middle Column - Conversation */}
        <div className="lg:col-span-1">
          <div className="bg-card border rounded-lg h-full min-h-[600px]">
            <ConversationHistory />
          </div>
        </div>

        {/* Right Column - Ticket Summary (conditional) */}
        <div className="lg:col-span-1">
          {showTicketSummary ? (
            <TicketSummary
              onClose={() => setShowTicketSummary(false)}
              onSave={(ticket) => {
                console.log('Ticket saved:', ticket)
                addNotification({
                  type: 'success',
                  message: 'Ticket created successfully'
                })
              }}
            />
          ) : (
            <div className="bg-card border rounded-lg p-6 space-y-6">
              <h2 className="font-semibold">Conversation Tools</h2>
              
              <div className="space-y-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <h3 className="font-medium mb-2">Session Statistics</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Messages:</span>
                      <span>{messages.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">User messages:</span>
                      <span>{messages.filter(m => m.role === 'user').length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">AI responses:</span>
                      <span>{messages.filter(m => m.role === 'assistant').length}</span>
                    </div>
                  </div>
                </div>

                {hasMessages && (
                  <Button
                    onClick={() => setShowTicketSummary(true)}
                    className="w-full"
                  >
                    <FileText size={16} className="mr-2" />
                    Generate Support Ticket
                  </Button>
                )}

                <div className="text-xs text-muted-foreground">
                  <p>
                    Start a conversation to see more options. 
                    Your conversation data is processed securely and can be exported at any time.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Mobile-friendly bottom action bar */}
      <div className="lg:hidden bg-card border rounded-lg p-4">
        <div className="flex items-center justify-center space-x-4">
          {hasMessages && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowTicketSummary(!showTicketSummary)}
              >
                <FileText size={16} className="mr-2" />
                Ticket
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportConversation}
              >
                <Download size={16} className="mr-2" />
                Export
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}