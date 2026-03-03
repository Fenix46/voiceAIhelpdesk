import { motion } from 'framer-motion'
import { 
  Heart,
  Smile,
  Meh, 
  Frown,
  RotateCcw,
  TrendingUp,
  TrendingDown
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SentimentData {
  score: number // -1 to 1
  confidence: number // 0 to 1
  emotion: 'joy' | 'sadness' | 'anger' | 'fear' | 'surprise' | 'neutral'
  trend: 'increasing' | 'decreasing' | 'stable'
  history: Array<{ timestamp: Date; score: number }>
}

interface SentimentIndicatorProps {
  sentiment: SentimentData
  size?: 'sm' | 'md' | 'lg'
  showHistory?: boolean
  showTrend?: boolean
  className?: string
}

export function SentimentIndicator({
  sentiment,
  size = 'md',
  showHistory = true,
  showTrend = true,
  className
}: SentimentIndicatorProps) {
  const getSentimentColor = (score: number) => {
    if (score > 0.3) return 'text-green-500'
    if (score > 0.1) return 'text-yellow-500'
    if (score > -0.1) return 'text-gray-500'
    if (score > -0.3) return 'text-orange-500'
    return 'text-red-500'
  }

  const getSentimentBg = (score: number) => {
    if (score > 0.3) return 'bg-green-100 dark:bg-green-900/20'
    if (score > 0.1) return 'bg-yellow-100 dark:bg-yellow-900/20'
    if (score > -0.1) return 'bg-gray-100 dark:bg-gray-900/20'
    if (score > -0.3) return 'bg-orange-100 dark:bg-orange-900/20'
    return 'bg-red-100 dark:bg-red-900/20'
  }

  const getSentimentIcon = (emotion: string, score: number) => {
    const sizeMap = { sm: 16, md: 20, lg: 24 }
    const iconSize = sizeMap[size]

    switch (emotion) {
      case 'joy':
        return <Smile size={iconSize} />
      case 'sadness':
        return <Frown size={iconSize} />
      case 'anger':
        return <Frown size={iconSize} />
      case 'neutral':
      default:
        return score > 0 ? <Smile size={iconSize} /> : score < 0 ? <Frown size={iconSize} /> : <Meh size={iconSize} />
    }
  }

  const getSentimentLabel = (score: number) => {
    if (score > 0.6) return 'Very Positive'
    if (score > 0.3) return 'Positive'
    if (score > 0.1) return 'Slightly Positive'
    if (score > -0.1) return 'Neutral'
    if (score > -0.3) return 'Slightly Negative'
    if (score > -0.6) return 'Negative'
    return 'Very Negative'
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp size={14} className="text-green-500" />
      case 'decreasing':
        return <TrendingDown size={14} className="text-red-500" />
      default:
        return <RotateCcw size={14} className="text-gray-500" />
    }
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Main Sentiment Display */}
      <div className={cn(
        "flex items-center space-x-3 p-3 rounded-lg border",
        getSentimentBg(sentiment.score)
      )}>
        <motion.div
          animate={{ 
            scale: [1, 1.1, 1],
            rotate: sentiment.emotion === 'anger' ? [0, -5, 5, 0] : 0
          }}
          transition={{ 
            duration: 2, 
            repeat: Infinity,
            ease: "easeInOut"
          }}
          className={getSentimentColor(sentiment.score)}
        >
          {getSentimentIcon(sentiment.emotion, sentiment.score)}
        </motion.div>

        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <span className="font-medium text-sm">
              {getSentimentLabel(sentiment.score)}
            </span>
            {showTrend && getTrendIcon(sentiment.trend)}
          </div>
          
          <div className="flex items-center space-x-2 mt-1">
            <div className="text-xs text-muted-foreground">
              Score: {sentiment.score.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground">
              Confidence: {Math.round(sentiment.confidence * 100)}%
            </div>
          </div>
        </div>

        {/* Confidence Ring */}
        <div className="relative w-8 h-8">
          <svg className="w-8 h-8 transform -rotate-90">
            <circle
              cx="16"
              cy="16"
              r="14"
              stroke="currentColor"
              strokeWidth="2"
              fill="transparent"
              className="text-muted-foreground/20"
            />
            <circle
              cx="16"
              cy="16"
              r="14"
              stroke="currentColor"
              strokeWidth="2"
              fill="transparent"
              className={getSentimentColor(sentiment.score)}
              strokeDasharray={`${2 * Math.PI * 14}`}
              strokeDashoffset={`${2 * Math.PI * 14 * (1 - sentiment.confidence)}`}
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* Sentiment History */}
      {showHistory && sentiment.history.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground">Recent History</h4>
          <div className="flex items-end space-x-1 h-16 p-2 bg-muted/20 rounded">
            {sentiment.history.slice(-20).map((point, index) => (
              <motion.div
                key={index}
                initial={{ height: 0 }}
                animate={{ 
                  height: `${Math.max(2, Math.abs(point.score) * 50)}%`,
                  backgroundColor: point.score > 0 ? '#22c55e' : point.score < 0 ? '#ef4444' : '#6b7280'
                }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                className="flex-1 rounded-sm min-w-[2px]"
                title={`${point.timestamp.toLocaleTimeString()}: ${point.score.toFixed(2)}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Emotional State Breakdown */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="p-2 bg-muted/20 rounded text-center">
          <div className="font-medium">Emotion</div>
          <div className="capitalize text-muted-foreground">{sentiment.emotion}</div>
        </div>
        <div className="p-2 bg-muted/20 rounded text-center">
          <div className="font-medium">Trend</div>
          <div className="capitalize text-muted-foreground flex items-center justify-center space-x-1">
            {getTrendIcon(sentiment.trend)}
            <span>{sentiment.trend}</span>
          </div>
        </div>
      </div>
    </div>
  )
}