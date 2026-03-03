import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  GitCompare,
  Play,
  Pause,
  RotateCcw,
  Target,
  Clock,
  Zap,
  Trophy,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart,
  Download,
  Settings,
  Plus,
  Trash2,
  CheckCircle,
  AlertCircle,
  Star,
  Brain,
  Activity,
  Cpu
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import { cn } from '@/lib/utils'

interface ModelConfig {
  id: string
  name: string
  provider: string
  version: string
  description: string
  parameters: {
    temperature: number
    maxTokens: number
    topP: number
    topK?: number
    frequencyPenalty?: number
    presencePenalty?: number
  }
  enabled: boolean
}

interface TestCase {
  id: string
  name: string
  prompt: string
  category: string
  expectedResponse?: string
  evaluationCriteria: string[]
  weight: number // for scoring
}

interface ModelResult {
  modelId: string
  testCaseId: string
  response: string
  metrics: {
    responseTime: number
    tokenCount: number
    tokensPerSecond: number
    cost: number
    latency: number
  }
  scores: {
    accuracy: number
    relevance: number
    coherence: number
    completeness: number
    creativity: number
    safety: number
  }
  timestamp: Date
  error?: string
}

interface ComparisonReport {
  id: string
  name: string
  models: string[]
  testCases: string[]
  results: ModelResult[]
  overallScores: Record<string, number>
  winner: string
  timestamp: Date
  summary: string
}

interface ModelComparisonProps {
  availableModels: ModelConfig[]
  testCases: TestCase[]
  onModelUpdate?: (model: ModelConfig) => void
  onTestCaseAdd?: (testCase: TestCase) => void
  onTestCaseDelete?: (testCaseId: string) => void
  onRunComparison?: (models: string[], testCases: string[]) => Promise<ModelResult[]>
  onReportSave?: (report: ComparisonReport) => void
  className?: string
}

export function ModelComparison({
  availableModels,
  testCases,
  onModelUpdate,
  onTestCaseAdd,
  onTestCaseDelete,
  onRunComparison,
  onReportSave,
  className
}: ModelComparisonProps) {
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [selectedTestCases, setSelectedTestCases] = useState<string[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [currentResults, setCurrentResults] = useState<ModelResult[]>([])
  const [completedTests, setCompletedTests] = useState(0)
  const [totalTests, setTotalTests] = useState(0)
  const [showModelConfig, setShowModelConfig] = useState<string | null>(null)
  const [newTestCase, setNewTestCase] = useState({
    name: '',
    prompt: '',
    category: 'general',
    expectedResponse: '',
    evaluationCriteria: [''],
    weight: 1
  })
  const [showTestCaseEditor, setShowTestCaseEditor] = useState(false)
  const [viewMode, setViewMode] = useState<'table' | 'charts' | 'radar'>('table')

  // Calculate comparison statistics
  const comparisonStats = useMemo(() => {
    if (currentResults.length === 0) return null

    const modelStats: Record<string, {
      avgResponseTime: number
      avgTokensPerSecond: number
      avgCost: number
      avgScore: number
      testCount: number
      errors: number
    }> = {}

    currentResults.forEach(result => {
      if (!modelStats[result.modelId]) {
        modelStats[result.modelId] = {
          avgResponseTime: 0,
          avgTokensPerSecond: 0,
          avgCost: 0,
          avgScore: 0,
          testCount: 0,
          errors: 0
        }
      }

      const stats = modelStats[result.modelId]
      stats.testCount++

      if (result.error) {
        stats.errors++
      } else {
        const overallScore = Object.values(result.scores).reduce((sum, score) => sum + score, 0) / Object.values(result.scores).length

        stats.avgResponseTime = (stats.avgResponseTime * (stats.testCount - 1) + result.metrics.responseTime) / stats.testCount
        stats.avgTokensPerSecond = (stats.avgTokensPerSecond * (stats.testCount - 1) + result.metrics.tokensPerSecond) / stats.testCount
        stats.avgCost = (stats.avgCost * (stats.testCount - 1) + result.metrics.cost) / stats.testCount
        stats.avgScore = (stats.avgScore * (stats.testCount - 1) + overallScore) / stats.testCount
      }
    })

    return modelStats
  }, [currentResults])

  const runComparison = async () => {
    if (!onRunComparison || selectedModels.length === 0 || selectedTestCases.length === 0) return

    setIsRunning(true)
    setCurrentResults([])
    setCompletedTests(0)
    setTotalTests(selectedModels.length * selectedTestCases.length)

    try {
      const results = await onRunComparison(selectedModels, selectedTestCases)
      setCurrentResults(results)
      setCompletedTests(results.length)
    } catch (error) {
      console.error('Comparison failed:', error)
    } finally {
      setIsRunning(false)
    }
  }

  const toggleModel = (modelId: string) => {
    setSelectedModels(prev =>
      prev.includes(modelId)
        ? prev.filter(id => id !== modelId)
        : [...prev, modelId]
    )
  }

  const toggleTestCase = (testCaseId: string) => {
    setSelectedTestCases(prev =>
      prev.includes(testCaseId)
        ? prev.filter(id => id !== testCaseId)
        : [...prev, testCaseId]
    )
  }

  const getModelName = (modelId: string) => {
    return availableModels.find(m => m.id === modelId)?.name || modelId
  }

  const getTestCaseName = (testCaseId: string) => {
    return testCases.find(tc => tc.id === testCaseId)?.name || testCaseId
  }

  const getBestModel = () => {
    if (!comparisonStats) return null
    
    let bestModel = ''
    let bestScore = 0
    
    Object.entries(comparisonStats).forEach(([modelId, stats]) => {
      if (stats.avgScore > bestScore) {
        bestScore = stats.avgScore
        bestModel = modelId
      }
    })
    
    return bestModel
  }

  const addTestCase = () => {
    if (onTestCaseAdd && newTestCase.name && newTestCase.prompt) {
      const testCase: TestCase = {
        id: `tc-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        ...newTestCase,
        evaluationCriteria: newTestCase.evaluationCriteria.filter(c => c.trim())
      }
      onTestCaseAdd(testCase)
      setNewTestCase({
        name: '',
        prompt: '',
        category: 'general',
        expectedResponse: '',
        evaluationCriteria: [''],
        weight: 1
      })
      setShowTestCaseEditor(false)
    }
  }

  // Prepare chart data
  const chartData = useMemo(() => {
    if (!comparisonStats) return []
    
    return Object.entries(comparisonStats).map(([modelId, stats]) => ({
      model: getModelName(modelId),
      score: Math.round(stats.avgScore * 100),
      responseTime: Math.round(stats.avgResponseTime),
      tokensPerSecond: Math.round(stats.avgTokensPerSecond),
      cost: stats.avgCost,
      errors: stats.errors
    }))
  }, [comparisonStats])

  // Prepare radar chart data
  const radarData = useMemo(() => {
    if (currentResults.length === 0) return []

    const categories = ['accuracy', 'relevance', 'coherence', 'completeness', 'creativity', 'safety']
    
    return categories.map(category => {
      const dataPoint: any = { category: category.charAt(0).toUpperCase() + category.slice(1) }
      
      selectedModels.forEach(modelId => {
        const modelResults = currentResults.filter(r => r.modelId === modelId && !r.error)
        if (modelResults.length > 0) {
          const avgScore = modelResults.reduce((sum, r) => sum + r.scores[category as keyof typeof r.scores], 0) / modelResults.length
          dataPoint[getModelName(modelId)] = Math.round(avgScore * 100)
        }
      })
      
      return dataPoint
    })
  }, [currentResults, selectedModels])

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <GitCompare size={20} className="text-primary" />
            <span>Model Comparison</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Compare AI model performance across different test cases
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button size="sm" variant="outline" onClick={() => setShowTestCaseEditor(true)}>
            <Plus size={14} className="mr-1" />
            Add Test Case
          </Button>
          <Button size="sm" variant="outline">
            <Download size={14} className="mr-1" />
            Export Results
          </Button>
        </div>
      </div>

      {/* Model Selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-medium">Select Models ({selectedModels.length})</h4>
          <div className="text-sm text-muted-foreground">
            Choose 2-6 models for comparison
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {availableModels.map(model => (
            <div
              key={model.id}
              className={cn(
                "p-3 border rounded-lg cursor-pointer transition-colors",
                selectedModels.includes(model.id) 
                  ? "border-primary bg-primary/5" 
                  : model.enabled 
                  ? "hover:bg-muted/50" 
                  : "opacity-50 cursor-not-allowed"
              )}
              onClick={() => model.enabled && toggleModel(model.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h5 className="font-medium">{model.name}</h5>
                    {selectedModels.includes(model.id) && (
                      <CheckCircle size={16} className="text-primary" />
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground mb-2">
                    {model.provider} • {model.version}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {model.description}
                  </p>
                </div>
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowModelConfig(showModelConfig === model.id ? null : model.id)
                  }}
                >
                  <Settings size={12} />
                </Button>
              </div>

              {/* Model Config */}
              <AnimatePresence>
                {showModelConfig === model.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="mt-3 pt-3 border-t"
                  >
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span>Temperature:</span>
                        <span>{model.parameters.temperature}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Max Tokens:</span>
                        <span>{model.parameters.maxTokens}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Top P:</span>
                        <span>{model.parameters.topP}</span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>

      {/* Test Case Selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-medium">Select Test Cases ({selectedTestCases.length})</h4>
          <div className="text-sm text-muted-foreground">
            Choose test cases to evaluate models
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-48 overflow-y-auto">
          {testCases.map(testCase => (
            <div
              key={testCase.id}
              className={cn(
                "p-3 border rounded-lg cursor-pointer transition-colors",
                selectedTestCases.includes(testCase.id)
                  ? "border-primary bg-primary/5"
                  : "hover:bg-muted/50"
              )}
              onClick={() => toggleTestCase(testCase.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h5 className="font-medium">{testCase.name}</h5>
                    {selectedTestCases.includes(testCase.id) && (
                      <CheckCircle size={16} className="text-primary" />
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground mb-1">
                    {testCase.category} • Weight: {testCase.weight}
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {testCase.prompt}
                  </p>
                </div>
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation()
                    onTestCaseDelete?.(testCase.id)
                  }}
                >
                  <Trash2 size={12} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Run Comparison */}
      <div className="flex items-center justify-between p-4 bg-card border rounded-lg">
        <div>
          <h4 className="font-medium mb-1">Ready to Compare</h4>
          <p className="text-sm text-muted-foreground">
            {selectedModels.length} models × {selectedTestCases.length} test cases = {selectedModels.length * selectedTestCases.length} total tests
          </p>
          {isRunning && (
            <div className="mt-2">
              <div className="w-64 bg-muted rounded-full h-2">
                <div 
                  className="h-2 bg-primary rounded-full transition-all"
                  style={{ width: `${(completedTests / totalTests) * 100}%` }}
                />
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {completedTests} / {totalTests} completed
              </div>
            </div>
          )}
        </div>
        
        <div className="flex space-x-2">
          <Button
            onClick={runComparison}
            disabled={isRunning || selectedModels.length < 2 || selectedTestCases.length === 0}
          >
            {isRunning ? (
              <>
                <div className="animate-spin mr-2">
                  <Activity size={16} />
                </div>
                Running...
              </>
            ) : (
              <>
                <Play size={16} className="mr-2" />
                Run Comparison
              </>
            )}
          </Button>
          
          {currentResults.length > 0 && (
            <Button variant="outline" onClick={() => setCurrentResults([])}>
              <RotateCcw size={16} className="mr-2" />
              Clear Results
            </Button>
          )}
        </div>
      </div>

      {/* Results */}
      {currentResults.length > 0 && (
        <div className="space-y-6">
          {/* Winner Banner */}
          {comparisonStats && getBestModel() && (
            <div className="p-4 bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900/10 dark:to-orange-900/10 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <div className="flex items-center space-x-3">
                <Trophy size={24} className="text-yellow-600" />
                <div>
                  <h4 className="font-semibold text-yellow-800 dark:text-yellow-200">
                    Best Overall Performance
                  </h4>
                  <p className="text-sm text-yellow-700 dark:text-yellow-300">
                    {getModelName(getBestModel()!)} achieved the highest average score of {(comparisonStats[getBestModel()!].avgScore * 100).toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* View Mode Selector */}
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Results</h4>
            <div className="flex space-x-1 bg-muted rounded-lg p-1">
              <button
                onClick={() => setViewMode('table')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'table' ? "bg-background shadow-sm" : "hover:bg-background/50"
                )}
              >
                Table
              </button>
              <button
                onClick={() => setViewMode('charts')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'charts' ? "bg-background shadow-sm" : "hover:bg-background/50"
                )}
              >
                Charts
              </button>
              <button
                onClick={() => setViewMode('radar')}
                className={cn(
                  "px-3 py-1 text-sm rounded-md transition-colors",
                  viewMode === 'radar' ? "bg-background shadow-sm" : "hover:bg-background/50"
                )}
              >
                Radar
              </button>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="p-3 bg-card border rounded-lg text-center">
              <div className="text-2xl font-bold">{selectedModels.length}</div>
              <div className="text-sm text-muted-foreground">Models</div>
            </div>
            <div className="p-3 bg-card border rounded-lg text-center">
              <div className="text-2xl font-bold">{selectedTestCases.length}</div>
              <div className="text-sm text-muted-foreground">Test Cases</div>
            </div>
            <div className="p-3 bg-card border rounded-lg text-center">
              <div className="text-2xl font-bold">{currentResults.length}</div>
              <div className="text-sm text-muted-foreground">Total Results</div>
            </div>
            <div className="p-3 bg-card border rounded-lg text-center">
              <div className="text-2xl font-bold text-red-600">
                {currentResults.filter(r => r.error).length}
              </div>
              <div className="text-sm text-muted-foreground">Errors</div>
            </div>
            <div className="p-3 bg-card border rounded-lg text-center">
              <div className="text-2xl font-bold">
                {comparisonStats ? Math.round(Object.values(comparisonStats).reduce((sum, stats) => sum + stats.avgResponseTime, 0) / Object.values(comparisonStats).length) : 0}ms
              </div>
              <div className="text-sm text-muted-foreground">Avg Response</div>
            </div>
          </div>

          {/* Results Display */}
          {viewMode === 'table' && comparisonStats && (
            <div className="overflow-x-auto">
              <table className="w-full border rounded-lg">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="p-3 text-left font-medium">Model</th>
                    <th className="p-3 text-center font-medium">Avg Score</th>
                    <th className="p-3 text-center font-medium">Response Time</th>
                    <th className="p-3 text-center font-medium">Tokens/sec</th>
                    <th className="p-3 text-center font-medium">Avg Cost</th>
                    <th className="p-3 text-center font-medium">Errors</th>
                    <th className="p-3 text-center font-medium">Tests</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(comparisonStats)
                    .sort(([,a], [,b]) => b.avgScore - a.avgScore)
                    .map(([modelId, stats], index) => (
                      <tr key={modelId} className="border-t">
                        <td className="p-3">
                          <div className="flex items-center space-x-2">
                            {index === 0 && <Star size={16} className="text-yellow-500" />}
                            <span className="font-medium">{getModelName(modelId)}</span>
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <div className={cn(
                            "font-medium",
                            stats.avgScore > 0.8 ? "text-green-600" :
                            stats.avgScore > 0.6 ? "text-yellow-600" : "text-red-600"
                          )}>
                            {(stats.avgScore * 100).toFixed(1)}%
                          </div>
                        </td>
                        <td className="p-3 text-center">{Math.round(stats.avgResponseTime)}ms</td>
                        <td className="p-3 text-center">{Math.round(stats.avgTokensPerSecond)}</td>
                        <td className="p-3 text-center">${stats.avgCost.toFixed(4)}</td>
                        <td className="p-3 text-center">
                          <span className={cn(
                            "font-medium",
                            stats.errors > 0 ? "text-red-600" : "text-green-600"
                          )}>
                            {stats.errors}
                          </span>
                        </td>
                        <td className="p-3 text-center">{stats.testCount}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          {viewMode === 'charts' && (
            <div className="space-y-6">
              {/* Score Chart */}
              <div>
                <h5 className="font-medium mb-3">Average Scores</h5>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="model" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="score" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Performance Chart */}
              <div>
                <h5 className="font-medium mb-3">Performance Metrics</h5>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="model" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="responseTime" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {viewMode === 'radar' && radarData.length > 0 && (
            <div>
              <h5 className="font-medium mb-3">Performance Radar</h5>
              <div className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="category" />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} />
                    {selectedModels.map((modelId, index) => (
                      <Radar
                        key={modelId}
                        name={getModelName(modelId)}
                        dataKey={getModelName(modelId)}
                        stroke={`hsl(${index * 60}, 70%, 50%)`}
                        fill={`hsl(${index * 60}, 70%, 50%)`}
                        fillOpacity={0.1}
                        strokeWidth={2}
                      />
                    ))}
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Test Case Editor Modal */}
      <AnimatePresence>
        {showTestCaseEditor && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => setShowTestCaseEditor(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-background p-6 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">Add Test Case</h3>
                <Button variant="outline" onClick={() => setShowTestCaseEditor(false)}>
                  <X size={16} />
                </Button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Name</label>
                    <input
                      type="text"
                      value={newTestCase.name}
                      onChange={(e) => setNewTestCase(prev => ({ ...prev, name: e.target.value }))}
                      className="w-full px-3 py-2 mt-1 text-sm border rounded"
                      placeholder="Test case name..."
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Category</label>
                    <select
                      value={newTestCase.category}
                      onChange={(e) => setNewTestCase(prev => ({ ...prev, category: e.target.value }))}
                      className="w-full px-3 py-2 mt-1 text-sm border rounded"
                    >
                      <option value="general">General</option>
                      <option value="reasoning">Reasoning</option>
                      <option value="creative">Creative</option>
                      <option value="technical">Technical</option>
                      <option value="conversation">Conversation</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium">Prompt</label>
                  <textarea
                    value={newTestCase.prompt}
                    onChange={(e) => setNewTestCase(prev => ({ ...prev, prompt: e.target.value }))}
                    className="w-full px-3 py-2 mt-1 text-sm border rounded resize-none"
                    rows={4}
                    placeholder="Enter the test prompt..."
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Weight</label>
                  <input
                    type="range"
                    min="0.5"
                    max="3"
                    step="0.5"
                    value={newTestCase.weight}
                    onChange={(e) => setNewTestCase(prev => ({ ...prev, weight: parseFloat(e.target.value) }))}
                    className="w-full mt-1"
                  />
                  <div className="text-xs text-center text-muted-foreground">{newTestCase.weight}x</div>
                </div>

                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setShowTestCaseEditor(false)}>
                    Cancel
                  </Button>
                  <Button onClick={addTestCase} disabled={!newTestCase.name || !newTestCase.prompt}>
                    <Plus size={14} className="mr-1" />
                    Add Test Case
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}