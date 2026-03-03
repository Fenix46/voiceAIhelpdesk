import { motion } from 'framer-motion'
import { 
  User,
  Calendar,
  MapPin,
  Phone,
  Mail,
  CreditCard,
  Hash,
  Clock,
  DollarSign,
  FileText
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Entity {
  text: string
  label: string
  start: number
  end: number
  confidence: number
  metadata?: {
    normalized?: string
    type?: string
    subtype?: string
  }
}

interface EntityHighlighterProps {
  text: string
  entities: Entity[]
  showLabels?: boolean
  showConfidence?: boolean
  highlightStyle?: 'underline' | 'background' | 'border'
  className?: string
}

export function EntityHighlighter({
  text,
  entities,
  showLabels = true,
  showConfidence = false,
  highlightStyle = 'background',
  className
}: EntityHighlighterProps) {
  const getEntityIcon = (label: string) => {
    const iconProps = { size: 12 }
    
    switch (label.toLowerCase()) {
      case 'person':
      case 'name':
        return <User {...iconProps} />
      case 'date':
      case 'time':
        return <Calendar {...iconProps} />
      case 'location':
      case 'address':
        return <MapPin {...iconProps} />
      case 'phone':
      case 'phone_number':
        return <Phone {...iconProps} />
      case 'email':
        return <Mail {...iconProps} />
      case 'credit_card':
      case 'card_number':
        return <CreditCard {...iconProps} />
      case 'number':
      case 'quantity':
        return <Hash {...iconProps} />
      case 'duration':
        return <Clock {...iconProps} />
      case 'money':
      case 'price':
      case 'amount':
        return <DollarSign {...iconProps} />
      default:
        return <FileText {...iconProps} />
    }
  }

  const getEntityColor = (label: string) => {
    const colors = {
      person: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800',
      name: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-800',
      date: 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800',
      time: 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/20 dark:text-green-300 dark:border-green-800',
      location: 'bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-800',
      address: 'bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-800',
      phone: 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-300 dark:border-yellow-800',
      phone_number: 'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-300 dark:border-yellow-800',
      email: 'bg-pink-100 text-pink-800 border-pink-200 dark:bg-pink-900/20 dark:text-pink-300 dark:border-pink-800',
      credit_card: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800',
      card_number: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-300 dark:border-red-800',
      number: 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800',
      quantity: 'bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900/20 dark:text-orange-300 dark:border-orange-800',
      money: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800',
      price: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800',
      amount: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-800'
    }
    
    return colors[label.toLowerCase() as keyof typeof colors] || 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-900/20 dark:text-gray-300 dark:border-gray-800'
  }

  const getHighlightStyle = (entity: Entity) => {
    const baseClasses = 'transition-all duration-200 cursor-pointer'
    const color = getEntityColor(entity.label)
    
    switch (highlightStyle) {
      case 'underline':
        return cn(baseClasses, 'underline decoration-2 underline-offset-2', color.replace(/bg-\w+-\d+/g, ''))
      case 'border':
        return cn(baseClasses, 'border-b-2 border-dashed', color.replace(/bg-\w+-\d+/g, ''))
      default: // background
        return cn(baseClasses, 'px-1 rounded-sm', color)
    }
  }

  // Sort entities by start position to avoid overlaps
  const sortedEntities = [...entities].sort((a, b) => a.start - b.start)

  // Create text segments with entity highlights
  const createHighlightedText = () => {
    if (sortedEntities.length === 0) {
      return <span>{text}</span>
    }

    const segments = []
    let currentIndex = 0

    sortedEntities.forEach((entity, index) => {
      // Add text before entity
      if (currentIndex < entity.start) {
        segments.push(
          <span key={`text-${index}`}>
            {text.slice(currentIndex, entity.start)}
          </span>
        )
      }

      // Add highlighted entity
      segments.push(
        <motion.span
          key={`entity-${index}`}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2, delay: index * 0.1 }}
          className={getHighlightStyle(entity)}
          title={`${entity.label} (${Math.round(entity.confidence * 100)}% confidence)${entity.metadata?.normalized ? ` - Normalized: ${entity.metadata.normalized}` : ''}`}
        >
          {entity.text}
        </motion.span>
      )

      currentIndex = entity.end
    })

    // Add remaining text
    if (currentIndex < text.length) {
      segments.push(
        <span key="text-end">
          {text.slice(currentIndex)}
        </span>
      )
    }

    return segments
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Highlighted Text */}
      <div className="p-3 bg-muted/20 rounded-lg leading-relaxed">
        {createHighlightedText()}
      </div>

      {/* Entity Legend */}
      {showLabels && entities.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground">Detected Entities:</h4>
          <div className="flex flex-wrap gap-2">
            {sortedEntities.map((entity, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: index * 0.05 }}
                className={cn(
                  "inline-flex items-center space-x-2 px-2 py-1 rounded-md text-xs border",
                  getEntityColor(entity.label)
                )}
              >
                {getEntityIcon(entity.label)}
                <span className="font-medium capitalize">{entity.label.replace('_', ' ')}</span>
                <span>"{entity.text}"</span>
                {showConfidence && (
                  <span className="opacity-75">
                    ({Math.round(entity.confidence * 100)}%)
                  </span>
                )}
                {entity.metadata?.normalized && entity.metadata.normalized !== entity.text && (
                  <span className="opacity-75">
                    → {entity.metadata.normalized}
                  </span>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Entity Statistics */}
      {entities.length > 0 && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2 bg-muted/20 rounded text-center">
            <div className="font-medium">{entities.length}</div>
            <div className="text-muted-foreground">Entities Found</div>
          </div>
          <div className="p-2 bg-muted/20 rounded text-center">
            <div className="font-medium">
              {Math.round((entities.reduce((sum, e) => sum + e.confidence, 0) / entities.length) * 100)}%
            </div>
            <div className="text-muted-foreground">Avg Confidence</div>
          </div>
        </div>
      )}

      {entities.length === 0 && (
        <div className="text-center text-sm text-muted-foreground py-4">
          No entities detected in this text
        </div>
      )}
    </div>
  )
}