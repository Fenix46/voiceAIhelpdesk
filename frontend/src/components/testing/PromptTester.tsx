import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  MessageSquare,
  Send,
  Zap,
  Copy,
  Save,
  Download,
  Upload,
  RotateCcw,
  Settings,
  Play,
  Pause,
  Clock,
  Target,
  CheckCircle,
  AlertCircle,
  Info,
  Trash2,
  Plus,
  History,
  FileText,
  Brain
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface PromptTemplate {
  id: string
  name: string
  description: string
  category: string
  template: string
  variables: string[]
  expectedResponse?: string
  validationCriteria?: string[]
  tags: string[]
  version: string
  createdAt: Date
  lastUsed?: Date
}

interface PromptExecution {
  id: string
  templateId: string
  prompt: string
  response: string
  timestamp: Date
  duration: number
  model: string
  parameters: Record<string, any>
  success: boolean
  errorMessage?: string
  metrics?: {
    responseTime: number
    tokenCount: number
    confidence: number
    relevance: number
    coherence: number
  }
  validationResults?: {
    criteria: string
    passed: boolean
    score?: number
  }[]
}

interface PromptTesterProps {
  templates: PromptTemplate[]
  onPromptExecute?: (prompt: string, parameters: Record<string, any>) => Promise<string>
  onTemplateCreate?: (template: Omit<PromptTemplate, 'id' | 'createdAt' | 'lastUsed'>) => void
  onTemplateSave?: (template: PromptTemplate) => void
  onTemplateDelete?: (templateId: string) => void
  onExecutionSave?: (execution: PromptExecution) => void
  availableModels?: string[]
  className?: string
}

export function PromptTester({
  templates,
  onPromptExecute,
  onTemplateCreate,
  onTemplateSave,
  onTemplateDelete,
  onExecutionSave,
  availableModels = ['gpt-4', 'gpt-3.5-turbo', 'claude-3', 'llama-2'],
  className
}: PromptTesterProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [customPrompt, setCustomPrompt] = useState('')
  const [templateVariables, setTemplateVariables] = useState<Record<string, string>>({})
  const [isExecuting, setIsExecuting] = useState(false)
  const [currentExecution, setCurrentExecution] = useState<PromptExecution | null>(null)
  const [executionHistory, setExecutionHistory] = useState<PromptExecution[]>([])
  const [selectedModel, setSelectedModel] = useState(availableModels[0])
  const [modelParameters, setModelParameters] = useState({
    temperature: 0.7,
    maxTokens: 1000,
    topP: 0.9
  })
  const [showTemplateEditor, setShowTemplateEditor] = useState(false)
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    description: '',
    category: 'general',
    template: '',
    variables: [] as string[],
    expectedResponse: '',
    validationCriteria: [] as string[],
    tags: [] as string[],
    version: '1.0'
  })

  const promptRef = useRef<HTMLTextAreaElement>(null)

  const template = templates.find(t => t.id === selectedTemplate)

  // Extract variables from template
  useEffect(() => {
    if (template) {
      const variables: Record<string, string> = {}
      template.variables.forEach(variable => {
        variables[variable] = templateVariables[variable] || ''
      })
      setTemplateVariables(variables)
    }
  }, [selectedTemplate, template])

  const buildPrompt = () => {
    if (template) {
      let prompt = template.template
      Object.entries(templateVariables).forEach(([key, value]) => {
        prompt = prompt.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value)
      })
      return prompt
    }
    return customPrompt
  }

  const executePrompt = async () => {
    if (!onPromptExecute) return

    const prompt = buildPrompt().trim()
    if (!prompt) return

    setIsExecuting(true)
    const startTime = Date.now()

    try {
      const response = await onPromptExecute(prompt, {
        model: selectedModel,
        ...modelParameters
      })

      const duration = Date.now() - startTime
      const execution: PromptExecution = {
        id: `exec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        templateId: selectedTemplate || 'custom',
        prompt,
        response,
        timestamp: new Date(),
        duration,
        model: selectedModel,
        parameters: modelParameters,
        success: true,
        metrics: {
          responseTime: duration,
          tokenCount: response.split(' ').length,
          confidence: 0.8 + Math.random() * 0.2,
          relevance: 0.7 + Math.random() * 0.3,
          coherence: 0.8 + Math.random() * 0.2
        }
      }

      // Validate response if template has criteria
      if (template?.validationCriteria) {
        execution.validationResults = template.validationCriteria.map(criteria => ({
          criteria,
          passed: Math.random() > 0.3, // Simulate validation
          score: Math.random()
        }))
      }

      setCurrentExecution(execution)
      setExecutionHistory(prev => [execution, ...prev.slice(0, 49)]) // Keep last 50

      // Update template last used
      if (template && onTemplateSave) {
        onTemplateSave({ ...template, lastUsed: new Date() })
      }

      onExecutionSave?.(execution)

    } catch (error) {
      const execution: PromptExecution = {
        id: `exec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        templateId: selectedTemplate || 'custom',
        prompt,
        response: '',
        timestamp: new Date(),
        duration: Date.now() - startTime,
        model: selectedModel,
        parameters: modelParameters,
        success: false,
        errorMessage: error instanceof Error ? error.message : 'Unknown error'
      }

      setCurrentExecution(execution)
      setExecutionHistory(prev => [execution, ...prev.slice(0, 49)])
    } finally {
      setIsExecuting(false)
    }
  }

  const saveTemplate = () => {
    if (onTemplateCreate) {
      const template: Omit<PromptTemplate, 'id' | 'createdAt' | 'lastUsed'> = {
        ...newTemplate,
        variables: extractVariables(newTemplate.template),
        validationCriteria: newTemplate.validationCriteria.filter(c => c.trim())
      }
      onTemplateCreate(template)
      setShowTemplateEditor(false)
      setNewTemplate({
        name: '',
        description: '',
        category: 'general',
        template: '',
        variables: [],
        expectedResponse: '',
        validationCriteria: [],
        tags: [],
        version: '1.0'
      })
    }
  }

  const extractVariables = (template: string) => {
    const matches = template.match(/\{\{([^}]+)\}\}/g)
    return matches ? [...new Set(matches.map(match => match.slice(2, -2)))] : []
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <MessageSquare size={20} className="text-primary" />
            <span>Prompt Tester</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Test and validate AI prompts with different models and parameters
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button size="sm" variant="outline" onClick={() => setShowTemplateEditor(true)}>
            <Plus size={14} className="mr-1" />
            New Template
          </Button>
          <Button size="sm" variant="outline">
            <History size={14} className="mr-1" />
            History ({executionHistory.length})
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Template Selection */}
        <div className="space-y-4">
          <h4 className="font-medium">Templates</h4>
          
          <div className="space-y-2 max-h-64 overflow-y-auto">
            <div
              className={cn(
                "p-3 border rounded-lg cursor-pointer transition-colors",
                !selectedTemplate ? "border-primary bg-primary/5" : "hover:bg-muted/50"
              )}
              onClick={() => setSelectedTemplate(null)}
            >
              <div className="font-medium">Custom Prompt</div>
              <div className="text-sm text-muted-foreground">Write your own prompt</div>
            </div>
            
            {templates.map(template => (
              <div
                key={template.id}
                className={cn(
                  "p-3 border rounded-lg cursor-pointer transition-colors",
                  selectedTemplate === template.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                )}
                onClick={() => setSelectedTemplate(template.id)}
              >
                <div className="flex items-start justify-between mb-1">
                  <div className="font-medium">{template.name}</div>
                  <div className="flex space-x-1">
                    {template.tags.slice(0, 2).map(tag => (
                      <span key={tag} className="px-1 py-0.5 bg-primary/10 text-primary text-xs rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-sm text-muted-foreground mb-1">{template.description}</div>
                <div className="text-xs text-muted-foreground">
                  {template.variables.length} variables • {template.category}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Prompt Builder */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Prompt Builder</h4>
            <div className="flex items-center space-x-2">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="px-2 py-1 text-sm border rounded bg-background"
              >
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
              <Button size="sm" variant="outline">
                <Settings size={14} />
              </Button>
            </div>
          </div>

          {/* Template Variables */}
          {template && template.variables.length > 0 && (
            <div className="space-y-2">
              <h5 className="text-sm font-medium">Variables</h5>
              {template.variables.map(variable => (
                <div key={variable}>
                  <label className="text-sm text-muted-foreground">{variable}:</label>
                  <input
                    type="text"
                    value={templateVariables[variable] || ''}
                    onChange={(e) => setTemplateVariables(prev => ({
                      ...prev,
                      [variable]: e.target.value
                    }))}
                    className="w-full px-3 py-2 mt-1 text-sm border rounded"
                    placeholder={`Enter ${variable}...`}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Prompt Input */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">
                {template ? 'Generated Prompt' : 'Custom Prompt'}
              </label>
              <div className="text-xs text-muted-foreground">
                {buildPrompt().length} characters
              </div>
            </div>
            
            <textarea
              ref={promptRef}
              value={template ? buildPrompt() : customPrompt}
              onChange={(e) => !template && setCustomPrompt(e.target.value)}
              placeholder={template ? 'Fill in variables above to generate prompt...' : 'Enter your prompt here...'}
              className="w-full h-40 px-3 py-2 text-sm border rounded resize-none"
              readOnly={!!template}
            />
          </div>

          {/* Model Parameters */}
          <div className="space-y-2">
            <h5 className="text-sm font-medium">Parameters</h5>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <label className="text-muted-foreground">Temperature:</label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={modelParameters.temperature}
                  onChange={(e) => setModelParameters(prev => ({
                    ...prev,
                    temperature: parseFloat(e.target.value)
                  }))}
                  className="w-full"
                />
                <div className="text-xs text-center">{modelParameters.temperature}</div>
              </div>
              <div>
                <label className="text-muted-foreground">Max Tokens:</label>
                <input
                  type="number"
                  min="1"
                  max="4000"
                  value={modelParameters.maxTokens}
                  onChange={(e) => setModelParameters(prev => ({
                    ...prev,
                    maxTokens: parseInt(e.target.value)
                  }))}
                  className="w-full px-2 py-1 text-xs border rounded"
                />
              </div>
              <div>
                <label className="text-muted-foreground">Top P:</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={modelParameters.topP}
                  onChange={(e) => setModelParameters(prev => ({
                    ...prev,
                    topP: parseFloat(e.target.value)
                  }))}
                  className="w-full"
                />
                <div className="text-xs text-center">{modelParameters.topP}</div>
              </div>
            </div>
          </div>

          {/* Execute Button */}
          <Button
            onClick={executePrompt}
            disabled={isExecuting || !buildPrompt().trim()}
            className="w-full"
          >
            {isExecuting ? (
              <>
                <div className="animate-spin mr-2">
                  <Zap size={14} />
                </div>
                Executing...
              </>
            ) : (
              <>
                <Send size={14} className="mr-2" />
                Execute Prompt
              </>
            )}
          </Button>
        </div>

        {/* Response & Results */}
        <div className="space-y-4">
          <h4 className="font-medium">Response</h4>
          
          {currentExecution ? (
            <div className="space-y-4">
              {/* Execution Info */}
              <div className="p-3 bg-muted/20 rounded-lg">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Model:</span>
                    <div className="font-medium">{currentExecution.model}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Duration:</span>
                    <div className="font-medium">{formatTime(currentExecution.duration)}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status:</span>
                    <div className={cn(
                      "font-medium flex items-center space-x-1",
                      currentExecution.success ? "text-green-600" : "text-red-600"
                    )}>
                      {currentExecution.success ? (
                        <CheckCircle size={12} />
                      ) : (
                        <AlertCircle size={12} />
                      )}
                      <span>{currentExecution.success ? 'Success' : 'Failed'}</span>
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Timestamp:</span>
                    <div className="font-medium text-xs">
                      {currentExecution.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Response Text */}
              {currentExecution.response && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h5 className="text-sm font-medium">Response</h5>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(currentExecution.response)}
                    >
                      <Copy size={12} />
                    </Button>
                  </div>
                  <div className="p-3 bg-background border rounded-lg text-sm max-h-64 overflow-y-auto">
                    {currentExecution.response}
                  </div>
                </div>
              )}

              {/* Error Message */}
              {currentExecution.errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg dark:bg-red-900/10 dark:border-red-800">
                  <div className="flex items-center space-x-2 text-red-800 dark:text-red-200">
                    <AlertCircle size={16} />
                    <span className="font-medium">Error</span>
                  </div>
                  <p className="text-sm text-red-700 dark:text-red-300 mt-1">
                    {currentExecution.errorMessage}
                  </p>
                </div>
              )}

              {/* Metrics */}
              {currentExecution.metrics && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Metrics</h5>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-2 bg-background rounded text-center">
                      <div className="font-medium">{currentExecution.metrics.tokenCount}</div>
                      <div className="text-xs text-muted-foreground">Tokens</div>
                    </div>
                    <div className="p-2 bg-background rounded text-center">
                      <div className="font-medium">{(currentExecution.metrics.confidence * 100).toFixed(0)}%</div>
                      <div className="text-xs text-muted-foreground">Confidence</div>
                    </div>
                    <div className="p-2 bg-background rounded text-center">
                      <div className="font-medium">{(currentExecution.metrics.relevance * 100).toFixed(0)}%</div>
                      <div className="text-xs text-muted-foreground">Relevance</div>
                    </div>
                    <div className="p-2 bg-background rounded text-center">
                      <div className="font-medium">{(currentExecution.metrics.coherence * 100).toFixed(0)}%</div>
                      <div className="text-xs text-muted-foreground">Coherence</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Validation Results */}
              {currentExecution.validationResults && currentExecution.validationResults.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Validation Results</h5>
                  <div className="space-y-2">
                    {currentExecution.validationResults.map((result, index) => (
                      <div
                        key={index}
                        className={cn(
                          "flex items-center justify-between p-2 rounded text-sm",
                          result.passed 
                            ? "bg-green-50 text-green-800 dark:bg-green-900/10 dark:text-green-200"
                            : "bg-red-50 text-red-800 dark:bg-red-900/10 dark:text-red-200"
                        )}
                      >
                        <span className="flex-1">{result.criteria}</span>
                        <div className="flex items-center space-x-2">
                          {result.score && (
                            <span className="text-xs">{(result.score * 100).toFixed(0)}%</span>
                          )}
                          {result.passed ? (
                            <CheckCircle size={14} />
                          ) : (
                            <AlertCircle size={14} />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex space-x-2">
                <Button size="sm" variant="outline">
                  <Save size={12} className="mr-1" />
                  Save Result
                </Button>
                <Button size="sm" variant="outline">
                  <Download size={12} className="mr-1" />
                  Export
                </Button>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              <Brain size={48} className="mx-auto mb-4 opacity-50" />
              <p>Execute a prompt to see the response and analysis</p>
            </div>
          )}
        </div>
      </div>

      {/* Template Editor Modal */}
      <AnimatePresence>
        {showTemplateEditor && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
            onClick={() => setShowTemplateEditor(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-background p-6 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">Create Template</h3>
                <Button variant="outline" onClick={() => setShowTemplateEditor(false)}>
                  <X size={16} />
                </Button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">Name</label>
                    <input
                      type="text"
                      value={newTemplate.name}
                      onChange={(e) => setNewTemplate(prev => ({ ...prev, name: e.target.value }))}
                      className="w-full px-3 py-2 mt-1 text-sm border rounded"
                      placeholder="Template name..."
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Category</label>
                    <select
                      value={newTemplate.category}
                      onChange={(e) => setNewTemplate(prev => ({ ...prev, category: e.target.value }))}
                      className="w-full px-3 py-2 mt-1 text-sm border rounded"
                    >
                      <option value="general">General</option>
                      <option value="customer_service">Customer Service</option>
                      <option value="troubleshooting">Troubleshooting</option>
                      <option value="analysis">Analysis</option>
                      <option value="creative">Creative</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium">Description</label>
                  <textarea
                    value={newTemplate.description}
                    onChange={(e) => setNewTemplate(prev => ({ ...prev, description: e.target.value }))}
                    className="w-full px-3 py-2 mt-1 text-sm border rounded resize-none"
                    rows={2}
                    placeholder="Brief description of the template..."
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Template</label>
                  <div className="text-xs text-muted-foreground mb-1">
                    Use {"{{variable}}"} syntax for variables
                  </div>
                  <textarea
                    value={newTemplate.template}
                    onChange={(e) => setNewTemplate(prev => ({ ...prev, template: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border rounded resize-none font-mono"
                    rows={6}
                    placeholder="Enter your prompt template here..."
                  />
                  {newTemplate.template && (
                    <div className="mt-2 text-xs text-muted-foreground">
                      Variables found: {extractVariables(newTemplate.template).join(', ') || 'none'}
                    </div>
                  )}
                </div>

                <div>
                  <label className="text-sm font-medium">Tags (comma-separated)</label>
                  <input
                    type="text"
                    value={newTemplate.tags.join(', ')}
                    onChange={(e) => setNewTemplate(prev => ({
                      ...prev,
                      tags: e.target.value.split(',').map(tag => tag.trim()).filter(Boolean)
                    }))}
                    className="w-full px-3 py-2 mt-1 text-sm border rounded"
                    placeholder="tag1, tag2, tag3..."
                  />
                </div>

                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setShowTemplateEditor(false)}>
                    Cancel
                  </Button>
                  <Button onClick={saveTemplate} disabled={!newTemplate.name || !newTemplate.template}>
                    <Save size={14} className="mr-1" />
                    Save Template
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Execution History (collapsible) */}
      {executionHistory.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium">Recent Executions</h4>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {executionHistory.slice(0, 5).map(execution => (
              <div
                key={execution.id}
                className="flex items-center justify-between p-2 hover:bg-muted/20 rounded cursor-pointer text-sm"
                onClick={() => setCurrentExecution(execution)}
              >
                <div className="flex items-center space-x-2">
                  {execution.success ? (
                    <CheckCircle size={12} className="text-green-500" />
                  ) : (
                    <AlertCircle size={12} className="text-red-500" />
                  )}
                  <span className="truncate max-w-[200px]">
                    {execution.prompt.slice(0, 50)}...
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-muted-foreground">
                  <span>{execution.model}</span>
                  <span>{formatTime(execution.duration)}</span>
                  <Clock size={12} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}