import { useState, useMemo } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { Button } from '@/components/ui/button'
import { 
  PieChart as PieChartIcon,
  BarChart3,
  TrendingUp,
  Tag,
  Filter,
  Eye
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CategoryData {
  category: string
  count: number
  percentage: number
  trend: 'up' | 'down' | 'stable'
  trendValue: number
  subcategories?: Array<{
    name: string
    count: number
    percentage: number
  }>
  avgResolutionTime?: number
  satisfactionScore?: number
}

interface CategoryDistributionProps {
  data: CategoryData[]
  title?: string
  showSubcategories?: boolean
  showTrends?: boolean
  className?: string
}

const COLORS = [
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // yellow
  '#ef4444', // red
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#f97316', // orange
  '#84cc16', // lime
  '#ec4899', // pink
  '#64748b'  // gray
]

export function CategoryDistribution({
  data,
  title = "Category Distribution",
  showSubcategories = true,
  showTrends = true,
  className
}: CategoryDistributionProps) {
  const [chartType, setChartType] = useState<'pie' | 'bar'>('pie')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<'count' | 'percentage' | 'name'>('count')

  // Sort and process data
  const sortedData = useMemo(() => {
    const sorted = [...data].sort((a, b) => {
      switch (sortBy) {
        case 'count':
          return b.count - a.count
        case 'percentage':
          return b.percentage - a.percentage
        case 'name':
          return a.category.localeCompare(b.category)
        default:
          return 0
      }
    })
    return sorted
  }, [data, sortBy])

  // Calculate totals
  const totals = useMemo(() => {
    const totalCount = data.reduce((sum, item) => sum + item.count, 0)
    const avgSatisfaction = data
      .filter(item => item.satisfactionScore)
      .reduce((sum, item, _, arr) => sum + (item.satisfactionScore! / arr.length), 0)
    const avgResolutionTime = data
      .filter(item => item.avgResolutionTime)
      .reduce((sum, item, _, arr) => sum + (item.avgResolutionTime! / arr.length), 0)

    return {
      totalCount,
      avgSatisfaction,
      avgResolutionTime,
      categories: data.length
    }
  }, [data])

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-card border rounded-lg p-3 shadow-lg">
          <p className="font-medium mb-2">{data.category}</p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between space-x-4">
              <span>Count:</span>
              <span className="font-medium">{data.count}</span>
            </div>
            <div className="flex justify-between space-x-4">
              <span>Percentage:</span>
              <span className="font-medium">{data.percentage.toFixed(1)}%</span>
            </div>
            {data.avgResolutionTime && (
              <div className="flex justify-between space-x-4">
                <span>Avg Resolution:</span>
                <span className="font-medium">{data.avgResolutionTime}min</span>
              </div>
            )}
            {data.satisfactionScore && (
              <div className="flex justify-between space-x-4">
                <span>Satisfaction:</span>
                <span className="font-medium">{data.satisfactionScore.toFixed(1)}/5</span>
              </div>
            )}
          </div>
        </div>
      )
    }
    return null
  }

  const getTrendIcon = (trend: string, value: number) => {
    if (trend === 'up') return <TrendingUp size={12} className="text-green-500" />
    if (trend === 'down') return <TrendingUp size={12} className="text-red-500 rotate-180" />
    return <div className="w-3 h-3 bg-gray-400 rounded-full" />
  }

  if (data.length === 0) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <Tag size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
        <h3 className="font-medium mb-2">No Category Data</h3>
        <p className="text-sm text-muted-foreground">
          Category distribution will appear here once data is available.
        </p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <Tag size={20} className="text-primary" />
            <span>{title}</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Breakdown of requests by category
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          {/* Chart Type Toggle */}
          <div className="flex space-x-1 bg-muted rounded-lg p-1">
            <button
              onClick={() => setChartType('pie')}
              className={cn(
                "p-1 rounded-md transition-colors",
                chartType === 'pie'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              <PieChartIcon size={14} />
            </button>
            <button
              onClick={() => setChartType('bar')}
              className={cn(
                "p-1 rounded-md transition-colors",
                chartType === 'bar'
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              <BarChart3 size={14} />
            </button>
          </div>

          {/* Sort Options */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md bg-background"
          >
            <option value="count">Sort by Count</option>
            <option value="percentage">Sort by Percentage</option>
            <option value="name">Sort by Name</option>
          </select>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">{totals.totalCount}</div>
          <div className="text-sm text-muted-foreground">Total Items</div>
        </div>
        <div className="p-4 bg-card border rounded-lg text-center">
          <div className="text-2xl font-bold">{totals.categories}</div>
          <div className="text-sm text-muted-foreground">Categories</div>
        </div>
        {totals.avgSatisfaction > 0 && (
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className="text-2xl font-bold">{totals.avgSatisfaction.toFixed(1)}</div>
            <div className="text-sm text-muted-foreground">Avg Satisfaction</div>
          </div>
        )}
        {totals.avgResolutionTime > 0 && (
          <div className="p-4 bg-card border rounded-lg text-center">
            <div className="text-2xl font-bold">{totals.avgResolutionTime.toFixed(0)}min</div>
            <div className="text-sm text-muted-foreground">Avg Resolution</div>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'pie' ? (
                <PieChart>
                  <Pie
                    data={sortedData}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="count"
                    onClick={(entry) => setSelectedCategory(
                      selectedCategory === entry.category ? null : entry.category
                    )}
                  >
                    {sortedData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={COLORS[index % COLORS.length]}
                        stroke={selectedCategory === entry.category ? "#000" : "none"}
                        strokeWidth={selectedCategory === entry.category ? 2 : 0}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                </PieChart>
              ) : (
                <BarChart data={sortedData}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis 
                    dataKey="category" 
                    tick={{ fontSize: 12 }}
                    angle={-45}
                    textAnchor="end"
                    height={80}
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar 
                    dataKey="count" 
                    fill="#3b82f6"
                    radius={[4, 4, 0, 0]}
                    onClick={(entry) => setSelectedCategory(
                      selectedCategory === entry.category ? null : entry.category
                    )}
                  />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>

        {/* Category List */}
        <div className="space-y-2">
          <h4 className="font-medium flex items-center space-x-2">
            <Eye size={16} />
            <span>Categories</span>
          </h4>
          
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {sortedData.map((category, index) => (
              <div 
                key={category.category}
                className={cn(
                  "p-3 border rounded-lg cursor-pointer transition-all",
                  selectedCategory === category.category 
                    ? "border-primary bg-primary/5" 
                    : "hover:bg-muted/50"
                )}
                onClick={() => setSelectedCategory(
                  selectedCategory === category.category ? null : category.category
                )}
              >
                <div className="flex items-center space-x-3">
                  <div 
                    className="w-4 h-4 rounded-full flex-shrink-0"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h5 className="font-medium text-sm truncate">
                        {category.category}
                      </h5>
                      {showTrends && (
                        <div className="flex items-center space-x-1">
                          {getTrendIcon(category.trend, category.trendValue)}
                          <span className="text-xs text-muted-foreground">
                            {category.trendValue.toFixed(1)}%
                          </span>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        {category.count} items
                      </span>
                      <span className="font-medium">
                        {category.percentage.toFixed(1)}%
                      </span>
                    </div>

                    {/* Progress bar */}
                    <div className="mt-2 w-full bg-muted rounded-full h-1">
                      <div 
                        className="h-1 rounded-full transition-all duration-300"
                        style={{ 
                          width: `${category.percentage}%`,
                          backgroundColor: COLORS[index % COLORS.length]
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Selected Category Details */}
      {selectedCategory && showSubcategories && (
        <div className="mt-6 p-4 bg-muted/20 rounded-lg">
          <h4 className="font-medium mb-3">
            {selectedCategory} - Subcategories
          </h4>
          
          {(() => {
            const selected = data.find(c => c.category === selectedCategory)
            if (!selected?.subcategories) {
              return <p className="text-sm text-muted-foreground">No subcategory data available</p>
            }
            
            return (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {selected.subcategories.map((sub, index) => (
                  <div key={sub.name} className="p-3 bg-background rounded-md">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{sub.name}</span>
                      <span className="text-sm text-muted-foreground">
                        {sub.percentage.toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {sub.count} items
                    </div>
                    <div className="mt-2 w-full bg-muted rounded-full h-1">
                      <div 
                        className="h-1 rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${(sub.percentage / selected.percentage) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}