import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { 
  Lightbulb,
  MessageSquare,
  ArrowRight,
  Clock,
  Star,
  CheckCircle,
  AlertCircle,
  Info,
  Zap,
  Brain,
  Users,
  TrendingUp
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Suggestion {
  id: string
  type: 'response' | 'action' | 'escalation' | 'information' | 'follow-up'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  title: string
  description: string
  confidence: number
  reasoning?: string
  suggestedResponse?: string
  actions?: Array<{
    label: string
    action: string
    data?: any
  }>
  metadata?: {
    estimatedTime?: number
    category?: string
    tags?: string[]
  }
}

interface SuggestionsPanelProps {
  suggestions: Suggestion[]
  onSuggestionAccept?: (suggestion: Suggestion) => void
  onSuggestionDismiss?: (suggestionId: string) => void
  maxSuggestions?: number
  autoUpdate?: boolean
  className?: string
}

export function SuggestionsPanel({
  suggestions,
  onSuggestionAccept,
  onSuggestionDismiss,
  maxSuggestions = 5,
  autoUpdate = true,
  className
}: SuggestionsPanelProps) {
  const [expandedSuggestion, setExpandedSuggestion] = useState<string | null>(null)
  const [dismissedSuggestions, setDismissedSuggestions] = useState<Set<string>>(new Set())

  const getSuggestionIcon = (type: string) => {
    const iconProps = { size: 16, className: "flex-shrink-0" }
    
    switch (type) {
      case 'response':
        return <MessageSquare {...iconProps} />
      case 'action':
        return <Zap {...iconProps} />
      case 'escalation':
        return <TrendingUp {...iconProps} />
      case 'information':
        return <Info {...iconProps} />
      case 'follow-up':
        return <Clock {...iconProps} />
      default:
        return <Lightbulb {...iconProps} />
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/10'
      case 'high':
        return 'border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-900/10'
      case 'medium':
        return 'border-yellow-300 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/10'
      default:
        return 'border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/10'
    }
  }

  const getPriorityIcon = (priority: string) => {
    const iconProps = { size: 12 }
    
    switch (priority) {
      case 'urgent':
        return <AlertCircle {...iconProps} className="text-red-600" />
      case 'high':
        return <AlertCircle {...iconProps} className="text-orange-600" />
      case 'medium':
        return <Info {...iconProps} className="text-yellow-600" />
      default:
        return <CheckCircle {...iconProps} className="text-blue-600" />
    }
  }

  const handleAccept = (suggestion: Suggestion) => {
    onSuggestionAccept?.(suggestion)
  }

  const handleDismiss = (suggestionId: string) => {
    setDismissedSuggestions(prev => new Set([...prev, suggestionId]))
    onSuggestionDismiss?.(suggestionId)
  }

  const activeSuggestions = suggestions
    .filter(s => !dismissedSuggestions.has(s.id))
    .sort((a, b) => {
      // Sort by priority first, then confidence
      const priorityOrder = { urgent: 4, high: 3, medium: 2, low: 1 }
      const priorityDiff = priorityOrder[b.priority] - priorityOrder[a.priority]
      if (priorityDiff !== 0) return priorityDiff
      return b.confidence - a.confidence
    })
    .slice(0, maxSuggestions)

  if (activeSuggestions.length === 0) {
    return (
      <div className={cn("p-4 text-center text-muted-foreground", className)}>
        <Brain size={32} className="mx-auto mb-2 opacity-50" />
        <p className="text-sm">No suggestions available</p>
        <p className="text-xs mt-1">AI will provide recommendations as the conversation progresses</p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Brain size={18} className="text-primary" />
          <h3 className="font-semibold text-sm">AI Suggestions</h3>
        </div>
        <div className="flex items-center space-x-1 text-xs text-muted-foreground">
          <Users size={12} />
          <span>{activeSuggestions.length}</span>
        </div>
      </div>

      {/* Suggestions */}
      <AnimatePresence>
        {activeSuggestions.map((suggestion, index) => (
          <motion.div
            key={suggestion.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2, delay: index * 0.05 }}
            className={cn(
              "border rounded-lg p-3 transition-all duration-200",
              getPriorityColor(suggestion.priority),
              expandedSuggestion === suggestion.id && "ring-2 ring-primary/20"
            )}
          >
            {/* Header */}
            <div className="flex items-start space-x-2 mb-2">
              {getSuggestionIcon(suggestion.type)}
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center space-x-2 mb-1">
                  <h4 className="font-medium text-sm truncate">
                    {suggestion.title}
                  </h4>
                  <div className="flex items-center space-x-1">
                    {getPriorityIcon(suggestion.priority)}
                    <span className="text-xs capitalize">{suggestion.priority}</span>
                  </div>
                </div>
                
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {suggestion.description}
                </p>
              </div>

              {/* Confidence Score */}
              <div className="flex items-center space-x-1">
                <Star 
                  size={12} 
                  className={cn(
                    suggestion.confidence >= 0.8 ? "text-yellow-500 fill-current" :
                    suggestion.confidence >= 0.6 ? "text-yellow-500" : "text-gray-400"
                  )} 
                />
                <span className="text-xs text-muted-foreground">
                  {Math.round(suggestion.confidence * 100)}%
                </span>
              </div>
            </div>

            {/* Metadata */}
            {suggestion.metadata && (
              <div className="flex items-center space-x-2 text-xs text-muted-foreground mb-2">
                {suggestion.metadata.estimatedTime && (
                  <div className="flex items-center space-x-1">
                    <Clock size={10} />
                    <span>{suggestion.metadata.estimatedTime}min</span>
                  </div>
                )}
                {suggestion.metadata.category && (
                  <span className="px-2 py-1 bg-muted rounded-full">
                    {suggestion.metadata.category}
                  </span>
                )}
              </div>
            )}

            {/* Suggested Response */}
            {suggestion.suggestedResponse && (
              <div className="bg-muted/50 rounded p-2 text-xs italic mb-2">
                "{suggestion.suggestedResponse}"
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between">
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  onClick={() => handleAccept(suggestion)}
                  className="h-7 px-2 text-xs"
                >
                  <CheckCircle size={12} className="mr-1" />
                  Accept
                </Button>
                
                {suggestion.actions && suggestion.actions.length > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setExpandedSuggestion(
                      expandedSuggestion === suggestion.id ? null : suggestion.id
                    )}
                    className="h-7 px-2 text-xs"
                  >
                    Actions
                    <ArrowRight 
                      size={12} 
                      className={cn(
                        "ml-1 transition-transform",
                        expandedSuggestion === suggestion.id && "rotate-90"
                      )} 
                    />
                  </Button>
                )}
              </div>

              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleDismiss(suggestion.id)}
                className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
              >
                Dismiss
              </Button>
            </div>

            {/* Expanded Actions */}
            <AnimatePresence>
              {expandedSuggestion === suggestion.id && suggestion.actions && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-3 pt-3 border-t space-y-2"
                >
                  {suggestion.reasoning && (
                    <div className="text-xs text-muted-foreground italic">
                      <strong>Reasoning:</strong> {suggestion.reasoning}
                    </div>
                  )}
                  
                  <div className="space-y-1">
                    {suggestion.actions.map((action, actionIndex) => (
                      <Button
                        key={actionIndex}
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          // Handle action execution
                          console.log('Executing action:', action)
                        }}
                        className="w-full justify-start h-7 text-xs"
                      >
                        <ArrowRight size={10} className="mr-2" />
                        {action.label}
                      </Button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Summary */}
      {activeSuggestions.length > 0 && (
        <div className="text-xs text-muted-foreground text-center pt-2 border-t">
          {activeSuggestions.filter(s => s.priority === 'urgent' || s.priority === 'high').length > 0 ? (
            <span className="text-orange-600 font-medium">
              {activeSuggestions.filter(s => s.priority === 'urgent' || s.priority === 'high').length} high-priority suggestions
            </span>
          ) : (
            <span>
              All suggestions reviewed • Avg confidence: {Math.round(activeSuggestions.reduce((sum, s) => sum + s.confidence, 0) / activeSuggestions.length * 100)}%
            </span>
          )}
        </div>
      )}
    </div>
  )
}