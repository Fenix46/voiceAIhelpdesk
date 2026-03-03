import { motion } from 'framer-motion'
import { 
  Shield,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Info,
  BarChart3
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ConfidenceData {
  overall: number
  breakdown: {
    transcription: number
    intent: number
    sentiment: number
    entities: number
    response: number
  }
  factors: Array<{
    name: string
    impact: 'positive' | 'negative' | 'neutral'
    value: number
    description: string
  }>
  trend: 'increasing' | 'decreasing' | 'stable'
  history: Array<{
    timestamp: Date
    score: number
    event?: string
  }>
}

interface ConfidenceScoreProps {
  confidence: ConfidenceData
  size?: 'sm' | 'md' | 'lg'
  showBreakdown?: boolean
  showFactors?: boolean
  showTrend?: boolean
  className?: string
}

export function ConfidenceScore({
  confidence,
  size = 'md',
  showBreakdown = true,
  showFactors = true,
  showTrend = true,
  className
}: ConfidenceScoreProps) {
  const getConfidenceLevel = (score: number) => {
    if (score >= 0.9) return { label: 'Excellent', color: 'text-green-600', bg: 'bg-green-100 dark:bg-green-900/20' }
    if (score >= 0.8) return { label: 'High', color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-900/10' }
    if (score >= 0.7) return { label: 'Good', color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/10' }
    if (score >= 0.6) return { label: 'Fair', color: 'text-yellow-500', bg: 'bg-yellow-50 dark:bg-yellow-900/10' }
    if (score >= 0.4) return { label: 'Low', color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/10' }
    return { label: 'Poor', color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-900/10' }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUp size={14} className="text-green-500" />
      case 'decreasing':
        return <TrendingDown size={14} className="text-red-500" />
      default:
        return <BarChart3 size={14} className="text-gray-500" />
    }
  }

  const level = getConfidenceLevel(confidence.overall)
  const circumference = 2 * Math.PI * 40
  const strokeDasharray = `${circumference * confidence.overall} ${circumference}`

  const sizeClasses = {
    sm: { container: 'p-3', title: 'text-sm', score: 'text-lg', circle: 'w-16 h-16' },
    md: { container: 'p-4', title: 'text-base', score: 'text-xl', circle: 'w-20 h-20' },
    lg: { container: 'p-6', title: 'text-lg', score: 'text-2xl', circle: 'w-24 h-24' }
  }

  const classes = sizeClasses[size]

  return (
    <div className={cn("space-y-4", className)}>
      {/* Main Confidence Display */}
      <div className={cn(
        "flex items-center space-x-4 rounded-lg border",
        classes.container,
        level.bg
      )}>
        {/* Circular Progress */}
        <div className="relative">
          <svg className={cn("transform -rotate-90", classes.circle)}>
            <circle
              cx="50%"
              cy="50%"
              r="40"
              stroke="currentColor"
              strokeWidth="4"
              fill="transparent"
              className="text-muted-foreground/20"
            />
            <motion.circle
              cx="50%"
              cy="50%"
              r="40"
              stroke="currentColor"
              strokeWidth="4"
              fill="transparent"
              className={level.color}
              strokeDasharray={circumference}
              strokeDashoffset={circumference - (circumference * confidence.overall)}
              strokeLinecap="round"
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: circumference - (circumference * confidence.overall) }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <Shield size={size === 'sm' ? 16 : size === 'md' ? 20 : 24} className={level.color} />
          </div>
        </div>

        {/* Score and Level */}
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <h3 className={cn("font-bold", level.color, classes.score)}>
              {Math.round(confidence.overall * 100)}%
            </h3>
            {showTrend && getTrendIcon(confidence.trend)}
          </div>
          <div className="flex items-center space-x-2">
            <span className={cn("font-medium", classes.title)}>
              {level.label} Confidence
            </span>
            {confidence.overall < 0.6 && (
              <AlertTriangle size={14} className="text-orange-500" />
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            AI system confidence in current analysis
          </p>
        </div>
      </div>

      {/* Confidence Breakdown */}
      {showBreakdown && (
        <div className="space-y-3">
          <h4 className="font-medium text-sm flex items-center space-x-2">
            <BarChart3 size={16} />
            <span>Confidence Breakdown</span>
          </h4>
          
          <div className="grid grid-cols-1 gap-2">
            {Object.entries(confidence.breakdown).map(([key, value]) => {
              const itemLevel = getConfidenceLevel(value)
              return (
                <div key={key} className="flex items-center space-x-3">
                  <div className="w-20 text-xs text-muted-foreground capitalize">
                    {key}
                  </div>
                  <div className="flex-1 relative">
                    <div className="w-full bg-muted rounded-full h-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${value * 100}%` }}
                        transition={{ duration: 0.8, delay: 0.1 }}
                        className={cn(
                          "h-2 rounded-full transition-colors",
                          value >= 0.8 ? "bg-green-500" :
                          value >= 0.6 ? "bg-blue-500" :
                          value >= 0.4 ? "bg-yellow-500" : "bg-red-500"
                        )}
                      />
                    </div>
                  </div>
                  <div className="w-12 text-xs text-right font-medium">
                    {Math.round(value * 100)}%
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Confidence Factors */}
      {showFactors && confidence.factors.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-sm flex items-center space-x-2">
            <Info size={16} />
            <span>Influencing Factors</span>
          </h4>
          
          <div className="space-y-2">
            {confidence.factors.slice(0, 5).map((factor, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2, delay: index * 0.05 }}
                className="flex items-center space-x-3 p-2 rounded-md bg-muted/20"
              >
                <div className={cn(
                  "w-3 h-3 rounded-full",
                  factor.impact === 'positive' ? "bg-green-500" :
                  factor.impact === 'negative' ? "bg-red-500" : "bg-gray-500"
                )} />
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium">{factor.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {factor.impact === 'positive' ? '+' : factor.impact === 'negative' ? '-' : ''}
                      {Math.round(Math.abs(factor.value) * 100)}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-1">
                    {factor.description}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Historical Trend */}
      {showTrend && confidence.history.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-sm">Recent Trend</h4>
          <div className="flex items-end space-x-1 h-12 p-2 bg-muted/20 rounded">
            {confidence.history.slice(-15).map((point, index) => (
              <motion.div
                key={index}
                initial={{ height: 0 }}
                animate={{ height: `${point.score * 100}%` }}
                transition={{ duration: 0.3, delay: index * 0.02 }}
                className={cn(
                  "flex-1 rounded-sm min-w-[2px]",
                  point.score >= 0.8 ? "bg-green-500" :
                  point.score >= 0.6 ? "bg-blue-500" :
                  point.score >= 0.4 ? "bg-yellow-500" : "bg-red-500"
                )}
                title={`${point.timestamp.toLocaleTimeString()}: ${Math.round(point.score * 100)}%${point.event ? ` - ${point.event}` : ''}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Confidence Recommendations */}
      {confidence.overall < 0.7 && (
        <div className="p-3 bg-orange-50 dark:bg-orange-900/10 border border-orange-200 dark:border-orange-800 rounded-lg">
          <div className="flex items-start space-x-2">
            <AlertTriangle size={16} className="text-orange-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h5 className="font-medium text-sm text-orange-800 dark:text-orange-200">
                Low Confidence Detected
              </h5>
              <p className="text-xs text-orange-700 dark:text-orange-300">
                Consider reviewing the audio quality, checking for background noise, or asking for clarification.
              </p>
              <div className="flex flex-wrap gap-1 mt-2">
                <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/20 rounded-full text-xs">
                  Check audio quality
                </span>
                <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/20 rounded-full text-xs">
                  Reduce background noise
                </span>
                <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/20 rounded-full text-xs">
                  Ask for clarification
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}