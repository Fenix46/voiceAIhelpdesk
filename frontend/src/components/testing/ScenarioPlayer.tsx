import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Play,
  Pause,
  Square,
  SkipForward,
  SkipBack,
  Volume2,
  Clock,
  FileAudio,
  Settings,
  RotateCcw,
  Save,
  Download,
  Upload,
  CheckCircle,
  AlertCircle,
  Info,
  Target,
  Activity
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ScenarioStep {
  id: string
  type: 'customer_speech' | 'system_response' | 'operator_action' | 'pause' | 'validation'
  content: string
  duration?: number // seconds
  audioFile?: string
  expectedResponse?: string
  validationCriteria?: string[]
  metadata?: Record<string, any>
}

interface TestScenario {
  id: string
  name: string
  description: string
  category: string
  difficulty: 'easy' | 'medium' | 'hard'
  estimatedDuration: number // seconds
  steps: ScenarioStep[]
  expectedOutcomes: string[]
  tags: string[]
  version: string
  createdBy: string
  lastModified: Date
}

interface ScenarioResult {
  stepId: string
  success: boolean
  actualResponse?: string
  expectedResponse?: string
  errorMessage?: string
  duration: number
  timestamp: Date
  metrics?: Record<string, number>
}

interface ScenarioPlayerProps {
  scenarios: TestScenario[]
  selectedScenario?: string
  onScenarioSelect?: (scenarioId: string) => void
  onScenarioComplete?: (scenarioId: string, results: ScenarioResult[]) => void
  onStepComplete?: (stepId: string, result: ScenarioResult) => void
  isPlaying?: boolean
  className?: string
}

export function ScenarioPlayer({
  scenarios,
  selectedScenario,
  onScenarioSelect,
  onScenarioComplete,
  onStepComplete,
  isPlaying = false,
  className
}: ScenarioPlayerProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [playState, setPlayState] = useState<'idle' | 'playing' | 'paused' | 'completed'>('idle')
  const [stepResults, setStepResults] = useState<ScenarioResult[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [showValidation, setShowValidation] = useState(true)
  const [autoAdvance, setAutoAdvance] = useState(true)
  const [stepNotes, setStepNotes] = useState<Record<string, string>>({})
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const stepStartTime = useRef<number>(0)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const scenario = scenarios.find(s => s.id === selectedScenario)
  const currentStepData = scenario?.steps[currentStep]

  // Timer for step execution
  useEffect(() => {
    if (playState === 'playing' && currentStepData) {
      stepStartTime.current = Date.now()
      
      if (currentStepData.type === 'pause' && currentStepData.duration) {
        intervalRef.current = setTimeout(() => {
          completeCurrentStep(true)
        }, (currentStepData.duration * 1000) / playbackSpeed)
      }
    }

    return () => {
      if (intervalRef.current) {
        clearTimeout(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [playState, currentStep, playbackSpeed])

  // Update current time
  useEffect(() => {
    if (playState === 'playing') {
      const timer = setInterval(() => {
        setCurrentTime(prev => prev + 1)
      }, 1000 / playbackSpeed)
      return () => clearInterval(timer)
    }
  }, [playState, playbackSpeed])

  const startScenario = () => {
    setPlayState('playing')
    setCurrentStep(0)
    setCurrentTime(0)
    setStepResults([])
  }

  const pauseScenario = () => {
    setPlayState('paused')
    if (intervalRef.current) {
      clearTimeout(intervalRef.current)
      intervalRef.current = null
    }
  }

  const resumeScenario = () => {
    setPlayState('playing')
  }

  const stopScenario = () => {
    setPlayState('idle')
    setCurrentStep(0)
    setCurrentTime(0)
    if (intervalRef.current) {
      clearTimeout(intervalRef.current)
      intervalRef.current = null
    }
  }

  const nextStep = () => {
    if (scenario && currentStep < scenario.steps.length - 1) {
      setCurrentStep(prev => prev + 1)
    } else {
      completeScenario()
    }
  }

  const previousStep = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }

  const completeCurrentStep = (success: boolean, actualResponse?: string, errorMessage?: string) => {
    if (!currentStepData) return

    const stepResult: ScenarioResult = {
      stepId: currentStepData.id,
      success,
      actualResponse,
      expectedResponse: currentStepData.expectedResponse,
      errorMessage,
      duration: Date.now() - stepStartTime.current,
      timestamp: new Date(),
      metrics: {
        playbackSpeed,
        stepIndex: currentStep
      }
    }

    setStepResults(prev => [...prev, stepResult])
    onStepComplete?.(currentStepData.id, stepResult)

    if (autoAdvance) {
      setTimeout(nextStep, 500)
    }
  }

  const completeScenario = () => {
    setPlayState('completed')
    if (scenario) {
      onScenarioComplete?.(scenario.id, stepResults)
    }
  }

  const playStepAudio = async () => {
    if (currentStepData?.audioFile) {
      try {
        if (audioRef.current) {
          audioRef.current.src = currentStepData.audioFile
          audioRef.current.playbackRate = playbackSpeed
          await audioRef.current.play()
        }
      } catch (error) {
        console.error('Error playing audio:', error)
      }
    }
  }

  const getStepIcon = (step: ScenarioStep) => {
    switch (step.type) {
      case 'customer_speech': return <Volume2 size={16} className="text-blue-500" />
      case 'system_response': return <Activity size={16} className="text-green-500" />
      case 'operator_action': return <Target size={16} className="text-purple-500" />
      case 'pause': return <Clock size={16} className="text-gray-500" />
      case 'validation': return <CheckCircle size={16} className="text-orange-500" />
      default: return <Info size={16} className="text-gray-500" />
    }
  }

  const getStepStatus = (stepIndex: number) => {
    if (stepIndex < currentStep) return 'completed'
    if (stepIndex === currentStep) return playState === 'playing' ? 'active' : 'current'
    return 'pending'
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (!scenario) {
    return (
      <div className={cn("p-6 text-center", className)}>
        <FileAudio size={48} className="mx-auto mb-4 text-muted-foreground opacity-50" />
        <h3 className="font-medium mb-2">Select a Test Scenario</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Choose a scenario from the list to begin testing.
        </p>
        {scenarios.length > 0 && (
          <div className="max-w-md mx-auto space-y-2">
            {scenarios.slice(0, 5).map(s => (
              <Button
                key={s.id}
                variant="outline"
                onClick={() => onScenarioSelect?.(s.id)}
                className="w-full justify-start"
              >
                <div className="flex items-center justify-between w-full">
                  <span>{s.name}</span>
                  <span className="text-xs text-muted-foreground">{s.difficulty}</span>
                </div>
              </Button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <FileAudio size={20} className="text-primary" />
            <span>Scenario Player</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Execute test scenarios and validate system responses
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button size="sm" variant="outline" onClick={() => setShowValidation(!showValidation)}>
            <Settings size={14} className="mr-1" />
            Settings
          </Button>
        </div>
      </div>

      {/* Scenario Info */}
      <div className="p-4 bg-card border rounded-lg">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h4 className="font-medium text-lg">{scenario.name}</h4>
            <p className="text-sm text-muted-foreground mb-2">{scenario.description}</p>
            <div className="flex items-center space-x-4 text-xs text-muted-foreground">
              <span>Category: {scenario.category}</span>
              <span>Difficulty: <span className={cn(
                "capitalize font-medium",
                scenario.difficulty === 'easy' ? 'text-green-600' :
                scenario.difficulty === 'medium' ? 'text-yellow-600' : 'text-red-600'
              )}>{scenario.difficulty}</span></span>
              <span>Duration: {formatTime(scenario.estimatedDuration)}</span>
              <span>Steps: {scenario.steps.length}</span>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-1">
            {scenario.tags.map(tag => (
              <span key={tag} className="px-2 py-1 bg-primary/10 text-primary text-xs rounded">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-muted rounded-full h-2 mb-2">
          <div 
            className="h-2 bg-primary rounded-full transition-all duration-300"
            style={{ width: `${((currentStep + (playState === 'completed' ? 1 : 0)) / scenario.steps.length) * 100}%` }}
          />
        </div>
        <div className="text-xs text-muted-foreground text-right">
          Step {currentStep + 1} of {scenario.steps.length}
        </div>
      </div>

      {/* Player Controls */}
      <div className="flex items-center justify-center space-x-4 p-4 bg-card border rounded-lg">
        <Button
          variant="outline"
          onClick={previousStep}
          disabled={currentStep === 0 || playState === 'playing'}
        >
          <SkipBack size={16} />
        </Button>

        {playState === 'playing' ? (
          <Button onClick={pauseScenario}>
            <Pause size={16} className="mr-2" />
            Pause
          </Button>
        ) : playState === 'paused' ? (
          <Button onClick={resumeScenario}>
            <Play size={16} className="mr-2" />
            Resume
          </Button>
        ) : (
          <Button onClick={startScenario}>
            <Play size={16} className="mr-2" />
            Start Scenario
          </Button>
        )}

        <Button
          variant="outline"
          onClick={stopScenario}
          disabled={playState === 'idle'}
        >
          <Square size={16} />
        </Button>

        <Button
          variant="outline"
          onClick={nextStep}
          disabled={currentStep === scenario.steps.length - 1 || playState === 'playing'}
        >
          <SkipForward size={16} />
        </Button>

        <div className="flex items-center space-x-2 ml-4">
          <span className="text-sm text-muted-foreground">Speed:</span>
          <select
            value={playbackSpeed}
            onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
            className="px-2 py-1 text-sm border rounded"
            disabled={playState === 'playing'}
          >
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={1.5}>1.5x</option>
            <option value={2}>2x</option>
          </select>
        </div>

        <div className="text-sm font-mono ml-4">
          {formatTime(currentTime)}
        </div>
      </div>

      {/* Current Step */}
      {currentStepData && (
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="p-4 bg-primary/5 border border-primary/20 rounded-lg"
        >
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 mt-1">
              {getStepIcon(currentStepData)}
            </div>
            
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium capitalize">
                  {currentStepData.type.replace('_', ' ')} 
                  {currentStepData.duration && ` (${currentStepData.duration}s)`}
                </h4>
                
                <div className="flex items-center space-x-2">
                  {currentStepData.audioFile && (
                    <Button size="sm" variant="outline" onClick={playStepAudio}>
                      <Volume2 size={12} className="mr-1" />
                      Play Audio
                    </Button>
                  )}
                  
                  {playState !== 'playing' && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => completeCurrentStep(true)}
                      >
                        <CheckCircle size={12} className="mr-1" />
                        Pass
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => completeCurrentStep(false, undefined, 'Manual failure')}
                      >
                        <AlertCircle size={12} className="mr-1" />
                        Fail
                      </Button>
                    </>
                  )}
                </div>
              </div>
              
              <p className="text-sm mb-3">{currentStepData.content}</p>
              
              {currentStepData.expectedResponse && (
                <div className="p-2 bg-background rounded text-sm">
                  <span className="text-muted-foreground">Expected: </span>
                  <span>{currentStepData.expectedResponse}</span>
                </div>
              )}
              
              {currentStepData.validationCriteria && showValidation && (
                <div className="mt-2">
                  <span className="text-xs text-muted-foreground">Validation Criteria:</span>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-1">
                    {currentStepData.validationCriteria.map((criteria, index) => (
                      <li key={index} className="flex items-center space-x-2">
                        <div className="w-1 h-1 bg-muted-foreground rounded-full" />
                        <span>{criteria}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Step Notes */}
              <div className="mt-3">
                <textarea
                  placeholder="Add notes for this step..."
                  value={stepNotes[currentStepData.id] || ''}
                  onChange={(e) => setStepNotes(prev => ({
                    ...prev,
                    [currentStepData.id]: e.target.value
                  }))}
                  className="w-full px-3 py-2 text-sm border rounded resize-none"
                  rows={2}
                />
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* Steps Overview */}
      <div className="space-y-2">
        <h4 className="font-medium">Scenario Steps</h4>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {scenario.steps.map((step, index) => {
            const status = getStepStatus(index)
            const result = stepResults.find(r => r.stepId === step.id)
            
            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center space-x-3 p-3 rounded-lg border cursor-pointer transition-colors",
                  status === 'completed' ? "bg-green-50 border-green-200 dark:bg-green-900/10 dark:border-green-800" :
                  status === 'active' ? "bg-primary/5 border-primary/20" :
                  status === 'current' ? "bg-yellow-50 border-yellow-200 dark:bg-yellow-900/10 dark:border-yellow-800" :
                  "bg-muted/20 border-muted hover:bg-muted/40"
                )}
                onClick={() => setCurrentStep(index)}
              >
                <div className="flex-shrink-0">
                  {status === 'completed' ? (
                    result?.success ? (
                      <CheckCircle size={16} className="text-green-500" />
                    ) : (
                      <AlertCircle size={16} className="text-red-500" />
                    )
                  ) : (
                    getStepIcon(step)
                  )}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm truncate capitalize">
                      {index + 1}. {step.type.replace('_', ' ')}
                    </span>
                    {step.duration && (
                      <span className="text-xs text-muted-foreground">{step.duration}s</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{step.content}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Results Summary */}
      {stepResults.length > 0 && (
        <div className="p-4 bg-card border rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium">Test Results</h4>
            <div className="flex space-x-2">
              <Button size="sm" variant="outline">
                <Save size={14} className="mr-1" />
                Save Results
              </Button>
              <Button size="sm" variant="outline">
                <Download size={14} className="mr-1" />
                Export
              </Button>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {stepResults.filter(r => r.success).length}
              </div>
              <div className="text-sm text-muted-foreground">Passed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {stepResults.filter(r => !r.success).length}
              </div>
              <div className="text-sm text-muted-foreground">Failed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">
                {stepResults.length > 0 ? Math.round((stepResults.filter(r => r.success).length / stepResults.length) * 100) : 0}%
              </div>
              <div className="text-sm text-muted-foreground">Success Rate</div>
            </div>
          </div>
          
          {playState === 'completed' && (
            <div className="text-center">
              <Button onClick={() => onScenarioSelect?.('')}>
                <RotateCcw size={16} className="mr-2" />
                Run Another Scenario
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Settings Panel */}
      <AnimatePresence>
        {showValidation && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-4 bg-muted/20 rounded-lg"
          >
            <h4 className="font-medium mb-3">Playback Settings</h4>
            <div className="space-y-3">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={autoAdvance}
                  onChange={(e) => setAutoAdvance(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Auto-advance to next step</span>
              </label>
              
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={showValidation}
                  onChange={(e) => setShowValidation(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Show validation criteria</span>
              </label>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <audio ref={audioRef} />
    </div>
  )
}