import { useState, useRef, useCallback, useEffect } from 'react'

interface AudioProcessorConfig {
  noiseGate: {
    threshold: number // dB
    enabled: boolean
  }
  compressor: {
    ratio: number
    threshold: number // dB
    enabled: boolean
  }
  echoCancellation: {
    enabled: boolean
  }
  gain: {
    level: number // 0.0 to 2.0
  }
}

interface AudioMetrics {
  inputLevel: number
  outputLevel: number
  gateOpen: boolean
  compressionGain: number
  spectrum: number[]
  peak: number
}

export function useAudioProcessor() {
  const [isInitialized, setIsInitialized] = useState(false)
  const [metrics, setMetrics] = useState<AudioMetrics>({
    inputLevel: 0,
    outputLevel: 0,
    gateOpen: false,
    compressionGain: 1,
    spectrum: [],
    peak: 0
  })
  
  const audioContextRef = useRef<AudioContext | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  
  const [config, setConfig] = useState<AudioProcessorConfig>({
    noiseGate: {
      threshold: -50,
      enabled: true
    },
    compressor: {
      ratio: 4,
      threshold: -20,
      enabled: true
    },
    echoCancellation: {
      enabled: false
    },
    gain: {
      level: 1.0
    }
  })

  const initializeProcessor = useCallback(async () => {
    try {
      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false, // We'll do our own
          noiseSuppression: false, // We'll do our own
          autoGainControl: false, // We'll do our own
          sampleRate: 48000,
          channelCount: 1
        }
      })
      
      streamRef.current = stream

      // Create audio context
      const audioContext = new AudioContext()
      audioContextRef.current = audioContext
      
      // Load the AudioWorklet processor
      await audioContext.audioWorklet.addModule('/audio-processor.js')
      
      // Create source node
      const source = audioContext.createMediaStreamSource(stream)
      sourceRef.current = source
      
      // Create worklet node
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor')
      workletNodeRef.current = workletNode
      
      // Handle messages from worklet
      workletNode.port.onmessage = (event) => {
        const { type, data } = event.data
        
        switch (type) {
          case 'audioLevel':
            setMetrics(prev => ({
              ...prev,
              outputLevel: data.rms,
              peak: data.peak,
              gateOpen: data.gateOpen,
              compressionGain: data.compressionGain
            }))
            break
            
          case 'spectrum':
            setMetrics(prev => ({
              ...prev,
              spectrum: data
            }))
            break
        }
      }
      
      // Connect the audio graph
      source.connect(workletNode)
      workletNode.connect(audioContext.destination)
      
      setIsInitialized(true)
      
      // Send initial configuration
      updateProcessorConfig(config)
      
    } catch (error) {
      console.error('Failed to initialize audio processor:', error)
      throw error
    }
  }, [config])

  const updateProcessorConfig = useCallback((newConfig: AudioProcessorConfig) => {
    const workletNode = workletNodeRef.current
    if (!workletNode) return

    // Send configuration updates to worklet
    if (newConfig.noiseGate.enabled !== config.noiseGate.enabled || 
        newConfig.noiseGate.threshold !== config.noiseGate.threshold) {
      workletNode.port.postMessage({
        type: 'setNoiseGate',
        data: {
          threshold: newConfig.noiseGate.enabled ? newConfig.noiseGate.threshold : -100,
          enabled: newConfig.noiseGate.enabled
        }
      })
    }
    
    if (newConfig.compressor.enabled !== config.compressor.enabled || 
        newConfig.compressor.ratio !== config.compressor.ratio ||
        newConfig.compressor.threshold !== config.compressor.threshold) {
      workletNode.port.postMessage({
        type: 'setCompression',
        data: {
          ratio: newConfig.compressor.enabled ? newConfig.compressor.ratio : 1,
          threshold: newConfig.compressor.enabled ? newConfig.compressor.threshold : 0,
          enabled: newConfig.compressor.enabled
        }
      })
    }
    
    if (newConfig.echoCancellation.enabled !== config.echoCancellation.enabled) {
      workletNode.port.postMessage({
        type: 'setEchoCancellation',
        data: {
          enabled: newConfig.echoCancellation.enabled
        }
      })
    }
    
    if (newConfig.gain.level !== config.gain.level) {
      workletNode.port.postMessage({
        type: 'setGain',
        data: {
          level: newConfig.gain.level
        }
      })
    }

    setConfig(newConfig)
  }, [config])

  const getProcessedStream = useCallback((): MediaStream | null => {
    const audioContext = audioContextRef.current
    const workletNode = workletNodeRef.current
    
    if (!audioContext || !workletNode) return null

    try {
      // Create a MediaStreamDestination to get processed audio as a stream
      const destination = audioContext.createMediaStreamDestination()
      workletNode.connect(destination)
      
      return destination.stream
    } catch (error) {
      console.error('Failed to get processed stream:', error)
      return null
    }
  }, [])

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect()
      workletNodeRef.current = null
    }
    
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    
    setIsInitialized(false)
  }, [])

  // Preset configurations
  const presets = {
    default: {
      noiseGate: { threshold: -50, enabled: true },
      compressor: { ratio: 4, threshold: -20, enabled: true },
      echoCancellation: { enabled: false },
      gain: { level: 1.0 }
    },
    
    quiet: {
      noiseGate: { threshold: -40, enabled: true },
      compressor: { ratio: 6, threshold: -25, enabled: true },
      echoCancellation: { enabled: true },
      gain: { level: 1.2 }
    },
    
    noisy: {
      noiseGate: { threshold: -35, enabled: true },
      compressor: { ratio: 8, threshold: -15, enabled: true },
      echoCancellation: { enabled: true },
      gain: { level: 0.8 }
    },
    
    clean: {
      noiseGate: { threshold: -60, enabled: false },
      compressor: { ratio: 2, threshold: -10, enabled: false },
      echoCancellation: { enabled: false },
      gain: { level: 1.0 }
    }
  }

  const applyPreset = useCallback((presetName: keyof typeof presets) => {
    const preset = presets[presetName]
    if (preset) {
      updateProcessorConfig(preset)
    }
  }, [updateProcessorConfig])

  // Cleanup on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  return {
    isInitialized,
    config,
    metrics,
    initializeProcessor,
    updateProcessorConfig,
    getProcessedStream,
    cleanup,
    presets,
    applyPreset
  }
}