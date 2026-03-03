import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useAudioProcessor } from '@/hooks/useAudioProcessor'
import { 
  Volume2,
  Settings,
  Play,
  Pause,
  RotateCcw,
  Sliders,
  Activity,
  Shield,
  Zap
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface AudioProcessorControlsProps {
  className?: string
  showMetrics?: boolean
  showSpectrum?: boolean
}

export function AudioProcessorControls({
  className,
  showMetrics = true,
  showSpectrum = true
}: AudioProcessorControlsProps) {
  const {
    isInitialized,
    config,
    metrics,
    initializeProcessor,
    updateProcessorConfig,
    cleanup,
    presets,
    applyPreset
  } = useAudioProcessor()
  
  const [activeTab, setActiveTab] = useState<'controls' | 'presets' | 'metrics'>('controls')

  const handleConfigChange = (section: keyof typeof config, key: string, value: any) => {
    const newConfig = {
      ...config,
      [section]: {
        ...config[section],
        [key]: value
      }
    }
    updateProcessorConfig(newConfig)
  }

  const tabs = [
    { id: 'controls', label: 'Controls', icon: Sliders },
    { id: 'presets', label: 'Presets', icon: Settings },
    { id: 'metrics', label: 'Metrics', icon: Activity }
  ]

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg flex items-center space-x-2">
          <Volume2 size={20} className="text-primary" />
          <span>Audio Processor</span>
        </h3>
        
        <div className="flex items-center space-x-2">
          <div className={cn(
            "flex items-center space-x-1 px-2 py-1 rounded-full text-xs",
            isInitialized 
              ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-300"
              : "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-300"
          )}>
            <div className={cn(
              "w-2 h-2 rounded-full",
              isInitialized ? "bg-green-500" : "bg-gray-500"
            )} />
            <span>{isInitialized ? 'Active' : 'Inactive'}</span>
          </div>
          
          {!isInitialized ? (
            <Button size="sm" onClick={initializeProcessor}>
              <Play size={14} className="mr-1" />
              Start
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={cleanup}>
              <Pause size={14} className="mr-1" />
              Stop
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-muted rounded-lg p-1">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                "flex-1 flex items-center justify-center space-x-2 py-2 px-3 rounded-md text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-background shadow-sm"
                  : "hover:bg-background/50"
              )}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'controls' && (
        <div className="space-y-6">
          {/* Noise Gate */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Shield size={16} className="text-blue-500" />
                <h4 className="font-medium">Noise Gate</h4>
              </div>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={config.noiseGate.enabled}
                  onChange={(e) => handleConfigChange('noiseGate', 'enabled', e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Enabled</span>
              </label>
            </div>
            
            {config.noiseGate.enabled && (
              <div>
                <label className="text-sm text-muted-foreground">
                  Threshold: {config.noiseGate.threshold} dB
                </label>
                <input
                  type="range"
                  min="-80"
                  max="-10"
                  step="1"
                  value={config.noiseGate.threshold}
                  onChange={(e) => handleConfigChange('noiseGate', 'threshold', parseInt(e.target.value))}
                  className="w-full mt-1"
                />
              </div>
            )}
          </div>

          {/* Compressor */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Zap size={16} className="text-orange-500" />
                <h4 className="font-medium">Compressor</h4>
              </div>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={config.compressor.enabled}
                  onChange={(e) => handleConfigChange('compressor', 'enabled', e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Enabled</span>
              </label>
            </div>
            
            {config.compressor.enabled && (
              <div className="space-y-3">
                <div>
                  <label className="text-sm text-muted-foreground">
                    Ratio: {config.compressor.ratio}:1
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="0.5"
                    value={config.compressor.ratio}
                    onChange={(e) => handleConfigChange('compressor', 'ratio', parseFloat(e.target.value))}
                    className="w-full mt-1"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">
                    Threshold: {config.compressor.threshold} dB
                  </label>
                  <input
                    type="range"
                    min="-40"
                    max="0"
                    step="1"
                    value={config.compressor.threshold}
                    onChange={(e) => handleConfigChange('compressor', 'threshold', parseInt(e.target.value))}
                    className="w-full mt-1"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Gain */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Volume2 size={16} className="text-green-500" />
              <h4 className="font-medium">Gain Control</h4>
            </div>
            
            <div>
              <label className="text-sm text-muted-foreground">
                Level: {(config.gain.level * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={config.gain.level}
                onChange={(e) => handleConfigChange('gain', 'level', parseFloat(e.target.value))}
                className="w-full mt-1"
              />
            </div>
          </div>

          {/* Echo Cancellation */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Activity size={16} className="text-purple-500" />
                <h4 className="font-medium">Echo Cancellation</h4>
              </div>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={config.echoCancellation.enabled}
                  onChange={(e) => handleConfigChange('echoCancellation', 'enabled', e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Enabled</span>
              </label>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'presets' && (
        <div className="space-y-3">
          {Object.entries(presets).map(([name, preset]) => (
            <div key={name} className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <h4 className="font-medium capitalize">{name}</h4>
                <p className="text-sm text-muted-foreground">
                  {name === 'default' && 'Balanced settings for general use'}
                  {name === 'quiet' && 'Optimized for quiet environments'}
                  {name === 'noisy' && 'Heavy processing for noisy environments'}
                  {name === 'clean' && 'Minimal processing for high-quality audio'}
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => applyPreset(name as keyof typeof presets)}
                disabled={!isInitialized}
              >
                Apply
              </Button>
            </div>
          ))}
          
          <Button
            variant="outline"
            onClick={() => {
              // Reset to default
              applyPreset('default')
            }}
            className="w-full"
            disabled={!isInitialized}
          >
            <RotateCcw size={14} className="mr-2" />
            Reset to Default
          </Button>
        </div>
      )}

      {activeTab === 'metrics' && showMetrics && (
        <div className="space-y-4">
          {/* Audio Levels */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-muted/20 rounded-lg text-center">
              <div className="text-lg font-bold">
                {(metrics.outputLevel * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">Output Level</div>
            </div>
            <div className="p-3 bg-muted/20 rounded-lg text-center">
              <div className="text-lg font-bold">
                {(metrics.peak * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-muted-foreground">Peak</div>
            </div>
          </div>

          {/* Processing Status */}
          <div className="space-y-2">
            <div className="flex items-center justify-between p-2 bg-muted/20 rounded">
              <span className="text-sm">Noise Gate</span>
              <div className={cn(
                "flex items-center space-x-1",
                metrics.gateOpen ? "text-green-500" : "text-red-500"
              )}>
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  metrics.gateOpen ? "bg-green-500" : "bg-red-500"
                )} />
                <span className="text-xs">
                  {metrics.gateOpen ? 'Open' : 'Closed'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center justify-between p-2 bg-muted/20 rounded">
              <span className="text-sm">Compression Gain</span>
              <span className="text-sm font-medium">
                {(metrics.compressionGain * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Spectrum Display */}
          {showSpectrum && metrics.spectrum.length > 0 && (
            <div className="space-y-2">
              <h5 className="text-sm font-medium">Frequency Spectrum</h5>
              <div className="h-20 bg-muted/20 rounded flex items-end space-x-1 p-2">
                {metrics.spectrum.slice(0, 32).map((value, index) => (
                  <div
                    key={index}
                    className="flex-1 bg-primary rounded-sm"
                    style={{ height: `${Math.max(2, value * 100)}%` }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!isInitialized && (
        <div className="text-center py-8 text-muted-foreground">
          <Settings size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">Initialize the audio processor to begin processing</p>
        </div>
      )}
    </div>
  )
}