import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Smile, 
  Meh, 
  Frown, 
  TrendingUp, 
  TrendingDown, 
  Target,
  Award,
  AlertCircle,
  Star
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface SatisfactionData {
  currentScore: number // 0-5 scale
  target: number // target score
  totalResponses: number
  trend: 'up' | 'down' | 'stable'
  trendValue: number // percentage change
  breakdown: {
    excellent: number // 5 stars
    good: number     // 4 stars
    fair: number     // 3 stars
    poor: number     // 2 stars
    terrible: number // 1 star
  }
  timeframe: '24h' | '7d' | '30d'
  history?: Array<{
    timestamp: Date
    score: number
    responses: number
  }>
}

interface UserSatisfactionGaugeProps {
  data: SatisfactionData
  size?: 'sm' | 'md' | 'lg'
  showBreakdown?: boolean
  showTrend?: boolean
  animated?: boolean
  className?: string
}

export function UserSatisfactionGauge({
  data,
  size = 'md',
  showBreakdown = true,
  showTrend = true,
  animated = true,
  className
}: UserSatisfactionGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0)

  useEffect(() => {
    if (animated) {
      const timer = setTimeout(() => {
        setAnimatedScore(data.currentScore)
      }, 100)
      return () => clearTimeout(timer)
    } else {
      setAnimatedScore(data.currentScore)
    }
  }, [data.currentScore, animated])

  const sizeConfig = {
    sm: { radius: 80, strokeWidth: 8, textSize: 'text-xl', labelSize: 'text-sm' },
    md: { radius: 100, strokeWidth: 12, textSize: 'text-2xl', labelSize: 'text-base' },
    lg: { radius: 120, strokeWidth: 16, textSize: 'text-3xl', labelSize: 'text-lg' }
  }

  const config = sizeConfig[size]
  const circumference = 2 * Math.PI * config.radius
  const scorePercentage = (animatedScore / 5) * 100
  const targetPercentage = (data.target / 5) * 100

  const getScoreColor = (score: number) => {
    if (score >= 4.5) return '#22c55e' // green
    if (score >= 4.0) return '#84cc16' // lime  
    if (score >= 3.5) return '#eab308' // yellow
    if (score >= 3.0) return '#f97316' // orange
    if (score >= 2.0) return '#ef4444' // red
    return '#dc2626' // dark red
  }

  const getScoreLabel = (score: number) => {
    if (score >= 4.5) return 'Excellent'
    if (score >= 4.0) return 'Very Good'
    if (score >= 3.5) return 'Good'
    if (score >= 3.0) return 'Fair'
    if (score >= 2.0) return 'Poor'
    return 'Very Poor'
  }

  const getScoreIcon = (score: number) => {
    const iconSize = size === 'sm' ? 20 : size === 'md' ? 24 : 28
    if (score >= 4.0) return <Smile size={iconSize} className="text-green-500" />
    if (score >= 3.0) return <Meh size={iconSize} className="text-yellow-500" />
    return <Frown size={iconSize} className="text-red-500" />
  }

  const strokeDasharray = `${(scorePercentage / 100) * circumference * 0.75} ${circumference}`
  const targetStrokeDasharray = `${(targetPercentage / 100) * circumference * 0.75} ${circumference}`

  const totalBreakdown = Object.values(data.breakdown).reduce((sum, count) => sum + count, 0)

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <Star size={20} className="text-primary" />
            <span>Customer Satisfaction</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Based on {data.totalResponses.toLocaleString()} responses in the last {data.timeframe}
          </p>
        </div>
        
        {showTrend && (
          <div className={cn(
            "flex items-center space-x-2 px-3 py-1 rounded-full text-sm",
            data.trend === 'up' ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300" :
            data.trend === 'down' ? "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-300" :
            "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-300"
          )}>
            {data.trend === 'up' ? <TrendingUp size={16} /> : 
             data.trend === 'down' ? <TrendingDown size={16} /> : 
             <Target size={16} />}
            <span>{data.trend === 'stable' ? 'Stable' : `${data.trendValue.toFixed(1)}%`}</span>
          </div>
        )}
      </div>

      {/* Main Gauge */}
      <div className="flex justify-center">
        <div className="relative">
          <svg 
            width={config.radius * 2 + 40} 
            height={config.radius * 1.2 + 40}
            className="transform -rotate-90"
          >
            {/* Background Arc */}
            <path
              d={`M 20 ${config.radius + 20} A ${config.radius} ${config.radius} 0 0 1 ${config.radius * 2 + 20} ${config.radius + 20}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={config.strokeWidth}
              className="text-muted-foreground/20"
            />
            
            {/* Target Arc */}
            <motion.path
              d={`M 20 ${config.radius + 20} A ${config.radius} ${config.radius} 0 0 1 ${config.radius * 2 + 20} ${config.radius + 20}`}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeDasharray={targetStrokeDasharray}
              className="text-blue-400 opacity-50"
              initial={{ strokeDasharray: `0 ${circumference}` }}
              animate={{ strokeDasharray: targetStrokeDasharray }}
              transition={{ duration: 1, delay: 0.5 }}
            />
            
            {/* Score Arc */}
            <motion.path
              d={`M 20 ${config.radius + 20} A ${config.radius} ${config.radius} 0 0 1 ${config.radius * 2 + 20} ${config.radius + 20}`}
              fill="none"
              stroke={getScoreColor(animatedScore)}
              strokeWidth={config.strokeWidth}
              strokeDasharray={strokeDasharray}
              strokeLinecap="round"
              initial={{ strokeDasharray: `0 ${circumference}` }}
              animate={{ strokeDasharray: strokeDasharray }}
              transition={{ duration: 1.5, ease: "easeOut" }}
            />
          </svg>
          
          {/* Center Content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <motion.div 
              className={cn("font-bold", config.textSize)}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.5, delay: 1 }}
            >
              {animatedScore.toFixed(1)}
            </motion.div>
            <div className="text-xs text-muted-foreground mt-1">/ 5.0</div>
            <div className={cn("font-medium mt-2", config.labelSize)}>
              {getScoreLabel(animatedScore)}
            </div>
            <div className="mt-2">
              {getScoreIcon(animatedScore)}
            </div>
          </div>
        </div>
      </div>

      {/* Score vs Target Comparison */}
      <div className="grid grid-cols-3 gap-4 text-center">
        <div className="p-3 bg-card border rounded-lg">
          <div className="text-lg font-bold" style={{ color: getScoreColor(data.currentScore) }}>
            {data.currentScore.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">Current</div>
        </div>
        
        <div className="p-3 bg-card border rounded-lg">
          <div className="text-lg font-bold text-blue-600">
            {data.target.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">Target</div>
        </div>
        
        <div className="p-3 bg-card border rounded-lg">
          <div className={cn(
            "text-lg font-bold",
            data.currentScore >= data.target ? "text-green-600" : "text-red-600"
          )}>
            {data.currentScore >= data.target ? '+' : ''}
            {(data.currentScore - data.target).toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">Difference</div>
        </div>
      </div>

      {/* Performance Status */}
      <div className={cn(
        "p-4 rounded-lg border-l-4",
        data.currentScore >= data.target 
          ? "bg-green-50 border-green-500 dark:bg-green-900/10"
          : data.currentScore >= data.target - 0.5 
          ? "bg-yellow-50 border-yellow-500 dark:bg-yellow-900/10"
          : "bg-red-50 border-red-500 dark:bg-red-900/10"
      )}>
        <div className="flex items-start space-x-3">
          {data.currentScore >= data.target ? (
            <Award size={20} className="text-green-600 mt-0.5" />
          ) : data.currentScore >= data.target - 0.5 ? (
            <Target size={20} className="text-yellow-600 mt-0.5" />
          ) : (
            <AlertCircle size={20} className="text-red-600 mt-0.5" />
          )}
          <div>
            <h4 className="font-medium mb-1">
              {data.currentScore >= data.target 
                ? "Target Exceeded!" 
                : data.currentScore >= data.target - 0.5 
                ? "Close to Target" 
                : "Below Target"}
            </h4>
            <p className="text-sm text-muted-foreground">
              {data.currentScore >= data.target 
                ? `Satisfaction score is ${(data.currentScore - data.target).toFixed(1)} points above target. Great work!`
                : `Need to improve by ${(data.target - data.currentScore).toFixed(1)} points to reach target of ${data.target}.`}
            </p>
          </div>
        </div>
      </div>

      {/* Rating Breakdown */}
      {showBreakdown && totalBreakdown > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium">Rating Breakdown</h4>
          
          <div className="space-y-2">
            {[
              { stars: 5, label: 'Excellent', count: data.breakdown.excellent, color: '#22c55e' },
              { stars: 4, label: 'Good', count: data.breakdown.good, color: '#84cc16' },
              { stars: 3, label: 'Fair', count: data.breakdown.fair, color: '#eab308' },
              { stars: 2, label: 'Poor', count: data.breakdown.poor, color: '#f97316' },
              { stars: 1, label: 'Terrible', count: data.breakdown.terrible, color: '#ef4444' }
            ].map((rating) => {
              const percentage = (rating.count / totalBreakdown) * 100
              return (
                <div key={rating.stars} className="flex items-center space-x-3">
                  <div className="flex items-center space-x-1 w-16">
                    {Array.from({ length: rating.stars }).map((_, i) => (
                      <Star key={i} size={12} className="fill-current" style={{ color: rating.color }} />
                    ))}
                  </div>
                  
                  <div className="flex-1 relative">
                    <div className="w-full bg-muted rounded-full h-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${percentage}%` }}
                        transition={{ duration: 0.8, delay: 0.2 }}
                        className="h-2 rounded-full"
                        style={{ backgroundColor: rating.color }}
                      />
                    </div>
                  </div>
                  
                  <div className="w-16 text-sm text-right">
                    {rating.count} ({percentage.toFixed(1)}%)
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Historical Trend */}
      {data.history && data.history.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium">Recent Trend</h4>
          <div className="flex items-end space-x-1 h-16 p-2 bg-muted/20 rounded">
            {data.history.slice(-15).map((point, index) => (
              <motion.div
                key={index}
                initial={{ height: 0 }}
                animate={{ height: `${(point.score / 5) * 100}%` }}
                transition={{ duration: 0.3, delay: index * 0.02 }}
                className="flex-1 rounded-sm min-w-[2px]"
                style={{ backgroundColor: getScoreColor(point.score) }}
                title={`${point.timestamp.toLocaleDateString()}: ${point.score.toFixed(1)} (${point.responses} responses)`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}