import { motion } from 'framer-motion'
import { 
  Target,
  MessageSquare,
  HelpCircle,
  AlertTriangle,
  CheckCircle,
  FileText,
  Settings,
  Phone,
  Mail,
  User,
  CreditCard,
  ShoppingCart
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface IntentData {
  intent: string
  confidence: number
  category: string
  subIntents?: Array<{
    name: string
    confidence: number
  }>
  entities?: Array<{
    entity: string
    value: string
    confidence: number
  }>
  context?: string
}

interface IntentDisplayProps {
  intents: IntentData[]
  maxIntents?: number
  showEntities?: boolean
  showSubIntents?: boolean
  className?: string
}

export function IntentDisplay({
  intents,
  maxIntents = 3,
  showEntities = true,
  showSubIntents = true,
  className
}: IntentDisplayProps) {
  const getIntentIcon = (intent: string, category: string) => {
    const iconProps = { size: 16, className: "flex-shrink-0" }
    
    // Category-based icons
    if (category.toLowerCase().includes('support')) return <HelpCircle {...iconProps} />
    if (category.toLowerCase().includes('billing')) return <CreditCard {...iconProps} />
    if (category.toLowerCase().includes('order')) return <ShoppingCart {...iconProps} />
    if (category.toLowerCase().includes('account')) return <User {...iconProps} />
    if (category.toLowerCase().includes('technical')) return <Settings {...iconProps} />
    
    // Intent-based icons
    if (intent.toLowerCase().includes('greeting')) return <MessageSquare {...iconProps} />
    if (intent.toLowerCase().includes('complaint')) return <AlertTriangle {...iconProps} />
    if (intent.toLowerCase().includes('request')) return <FileText {...iconProps} />
    if (intent.toLowerCase().includes('confirmation')) return <CheckCircle {...iconProps} />
    if (intent.toLowerCase().includes('contact')) return <Phone {...iconProps} />
    if (intent.toLowerCase().includes('email')) return <Mail {...iconProps} />
    
    return <Target {...iconProps} />
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-100 dark:bg-green-900/20'
    if (confidence >= 0.6) return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/20'
    if (confidence >= 0.4) return 'text-orange-600 bg-orange-100 dark:bg-orange-900/20'
    return 'text-red-600 bg-red-100 dark:bg-red-900/20'
  }

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'High'
    if (confidence >= 0.6) return 'Medium'
    if (confidence >= 0.4) return 'Low'
    return 'Very Low'
  }

  const displayedIntents = intents.slice(0, maxIntents)

  if (displayedIntents.length === 0) {
    return (
      <div className={cn("p-4 text-center text-muted-foreground", className)}>
        <Target size={24} className="mx-auto mb-2 opacity-50" />
        <p className="text-sm">No intents detected yet</p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-3", className)}>
      {displayedIntents.map((intentData, index) => (
        <motion.div
          key={`${intentData.intent}-${index}`}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
          className="border rounded-lg p-3 bg-card"
        >
          {/* Main Intent */}
          <div className="flex items-center space-x-3 mb-2">
            {getIntentIcon(intentData.intent, intentData.category)}
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2 mb-1">
                <h4 className="font-medium text-sm truncate">
                  {intentData.intent.replace(/[_-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </h4>
                <span className={cn(
                  "px-2 py-1 rounded-full text-xs font-medium",
                  getConfidenceColor(intentData.confidence)
                )}>
                  {getConfidenceLabel(intentData.confidence)}
                </span>
              </div>
              
              <div className="flex items-center space-x-2 text-xs text-muted-foreground">
                <span className="bg-muted px-2 py-1 rounded capitalize">
                  {intentData.category}
                </span>
                <span>
                  {Math.round(intentData.confidence * 100)}% confidence
                </span>
              </div>
            </div>

            {/* Confidence Bar */}
            <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${intentData.confidence * 100}%` }}
                transition={{ duration: 0.8, delay: index * 0.2 }}
                className={cn(
                  "h-full transition-colors",
                  intentData.confidence >= 0.8 ? "bg-green-500" :
                  intentData.confidence >= 0.6 ? "bg-yellow-500" :
                  intentData.confidence >= 0.4 ? "bg-orange-500" : "bg-red-500"
                )}
              />
            </div>
          </div>

          {/* Context */}
          {intentData.context && (
            <div className="text-xs text-muted-foreground italic mb-2 pl-6">
              "{intentData.context}"
            </div>
          )}

          {/* Sub-intents */}
          {showSubIntents && intentData.subIntents && intentData.subIntents.length > 0 && (
            <div className="pl-6 space-y-1">
              <h5 className="text-xs font-medium text-muted-foreground">Related Intents:</h5>
              {intentData.subIntents.map((subIntent, subIndex) => (
                <div key={subIndex} className="flex items-center space-x-2 text-xs">
                  <div className="w-1 h-1 bg-muted-foreground rounded-full" />
                  <span className="flex-1">{subIntent.name}</span>
                  <span className="text-muted-foreground">
                    {Math.round(subIntent.confidence * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Entities */}
          {showEntities && intentData.entities && intentData.entities.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <h5 className="text-xs font-medium text-muted-foreground mb-2">Detected Entities:</h5>
              <div className="flex flex-wrap gap-1">
                {intentData.entities.map((entity, entityIndex) => (
                  <motion.div
                    key={entityIndex}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.2, delay: entityIndex * 0.05 }}
                    className="inline-flex items-center space-x-1 px-2 py-1 bg-muted rounded-full text-xs"
                  >
                    <span className="font-medium capitalize">{entity.entity}:</span>
                    <span className="text-primary">{entity.value}</span>
                    <span className="text-muted-foreground">
                      ({Math.round(entity.confidence * 100)}%)
                    </span>
                  </motion.div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      ))}

      {/* Intent Summary */}
      {intents.length > maxIntents && (
        <div className="text-center text-sm text-muted-foreground">
          Showing top {maxIntents} of {intents.length} detected intents
        </div>
      )}

      {/* Overall Confidence */}
      {intents.length > 0 && (
        <div className="flex items-center justify-between p-2 bg-muted/20 rounded text-sm">
          <span className="text-muted-foreground">Overall Classification Confidence:</span>
          <span className="font-medium">
            {Math.round((intents.reduce((sum, intent) => sum + intent.confidence, 0) / intents.length) * 100)}%
          </span>
        </div>
      )}
    </div>
  )
}