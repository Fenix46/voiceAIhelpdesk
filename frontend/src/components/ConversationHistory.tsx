import { useEffect, useRef } from 'react'
import { useConversationStore, type Message } from '@/store/conversationStore'
import { Button } from '@/components/ui/button'
import { format } from 'date-fns'
import { 
  User, 
  Bot, 
  Play, 
  Pause, 
  Volume2,
  Copy,
  Trash2
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface MessageBubbleProps {
  message: Message
  onPlayAudio?: (audioUrl: string) => void
}

function MessageBubble({ message, onPlayAudio }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(message.content)
  }

  return (
    <div className={cn(
      "flex gap-3 max-w-[80%] group",
      isUser ? "ml-auto flex-row-reverse" : "mr-auto"
    )}>
      {/* Avatar */}
      <div className={cn(
        "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
        isUser 
          ? "bg-primary text-primary-foreground" 
          : "bg-muted border"
      )}>
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      {/* Message content */}
      <div className={cn(
        "flex flex-col space-y-1",
        isUser ? "items-end" : "items-start"
      )}>
        <div className={cn(
          "px-4 py-2 rounded-lg max-w-full break-words",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-muted rounded-bl-sm"
        )}>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>

        {/* Message actions and metadata */}
        <div className={cn(
          "flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity",
          isUser ? "flex-row-reverse" : "flex-row"
        )}>
          <span className="text-xs text-muted-foreground">
            {format(message.timestamp, 'HH:mm')}
          </span>
          
          <div className="flex items-center gap-1">
            {message.audioUrl && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => onPlayAudio?.(message.audioUrl!)}
                aria-label="Play audio"
              >
                <Volume2 size={12} />
              </Button>
            )}
            
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={copyToClipboard}
              aria-label="Copy message"
            >
              <Copy size={12} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function ConversationHistory() {
  const { messages, clearConversation } = useConversationStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handlePlayAudio = (audioUrl: string) => {
    const audio = new Audio(audioUrl)
    audio.play().catch(console.error)
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-2">
          <Bot size={48} className="mx-auto text-muted-foreground" />
          <h3 className="font-medium text-muted-foreground">
            No conversation yet
          </h3>
          <p className="text-sm text-muted-foreground">
            Start recording to begin your conversation
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="font-semibold">Conversation</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={clearConversation}
          className="text-muted-foreground hover:text-destructive"
        >
          <Trash2 size={16} />
          <span className="ml-2">Clear</span>
        </Button>
      </div>

      {/* Messages */}
      <div 
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onPlayAudio={handlePlayAudio}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Stats */}
      <div className="border-t p-4">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{messages.length} messages</span>
          <span>
            {messages.filter(m => m.role === 'user').length} user • {' '}
            {messages.filter(m => m.role === 'assistant').length} assistant
          </span>
        </div>
      </div>
    </div>
  )
}