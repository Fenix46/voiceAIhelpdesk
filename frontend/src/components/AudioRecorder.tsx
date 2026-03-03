import { useState, useRef, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { useConversationStore } from '@/store/conversationStore'
import { useAppStore } from '@/store/appStore'
import { socketManager } from '@/lib/socket'
import { useVoiceActivation } from '@/hooks/useVoiceActivation'
import { usePushToTalk } from '@/hooks/usePushToTalk'
import { 
  Mic, 
  MicOff, 
  Square, 
  Play, 
  Pause,
  Volume2,
  VolumeX,
  Zap,
  Hand
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function AudioRecorder() {
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null)
  const [audioLevel, setAudioLevel] = useState(0)
  const [isInitialized, setIsInitialized] = useState(false)
  const [vadMode, setVadMode] = useState(false)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number>()
  
  const { 
    isRecording, 
    setRecording, 
    setProcessing,
    addMessage,
    sessionId,
    setSessionId
  } = useConversationStore()
  
  const { settings, addNotification } = useAppStore()

  // Voice Activation Detection
  const voiceActivation = useVoiceActivation({
    threshold: 0.1,
    silenceTimeout: 1500,
    minRecordingTime: 1000
  })

  // Push to Talk
  const pushToTalk = usePushToTalk({
    key: 'Space'
  })

  const initializeAudio = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: settings.noiseReduction,
          autoGainControl: true,
          sampleRate: 16000,
        } 
      })

      // Create MediaRecorder
      const recorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      })

      // Setup audio analysis
      audioContextRef.current = new AudioContext()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      analyserRef.current.fftSize = 256
      source.connect(analyserRef.current)

      // Setup recorder events
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          const socket = socketManager.getSocket()
          if (socket?.connected) {
            socket.emit('audio-chunk', {
              sessionId,
              audioData: event.data,
              timestamp: Date.now()
            })
          }
        }
      }

      recorder.onstart = () => {
        setRecording(true)
        if (!sessionId) {
          const newSessionId = crypto.randomUUID()
          setSessionId(newSessionId)
        }
        addNotification({
          type: 'info',
          message: 'Recording started'
        })
      }

      recorder.onstop = () => {
        setRecording(false)
        setProcessing(true)
        addNotification({
          type: 'info',
          message: 'Processing audio...'
        })
      }

      setMediaRecorder(recorder)
      setIsInitialized(true)
      
    } catch (error) {
      console.error('Error initializing audio:', error)
      addNotification({
        type: 'error',
        message: 'Failed to access microphone'
      })
    }
  }, [settings.noiseReduction, sessionId, setSessionId, setRecording, setProcessing, addNotification])

  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current) return

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)
    
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length
    setAudioLevel(average / 255)

    if (isRecording) {
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel)
    }
  }, [isRecording])

  useEffect(() => {
    if (isRecording && analyserRef.current) {
      updateAudioLevel()
    } else if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [isRecording, updateAudioLevel])

  useEffect(() => {
    // Setup socket listeners
    const socket = socketManager.connect()
    
    socket?.on('transcript-partial', (data) => {
      // Handle partial transcript updates
      console.log('Partial transcript:', data)
    })

    socket?.on('transcript-final', (data) => {
      setProcessing(false)
      addMessage({
        role: 'user',
        content: data.transcript
      })
      addNotification({
        type: 'success',
        message: 'Audio processed successfully'
      })
    })

    socket?.on('error', (error) => {
      setProcessing(false)
      setRecording(false)
      addNotification({
        type: 'error',
        message: error.message || 'An error occurred'
      })
    })

    return () => {
      socket?.off('transcript-partial')
      socket?.off('transcript-final')
      socket?.off('error')
    }
  }, [setProcessing, addMessage, addNotification])

  const startRecording = async () => {
    if (!isInitialized) {
      await initializeAudio()
      return
    }

    if (mediaRecorder && mediaRecorder.state === 'inactive') {
      mediaRecorder.start(100) // Send chunks every 100ms
    }
  }

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop()
    }
  }

  // Set up voice activation callbacks
  useEffect(() => {
    voiceActivation.setOnVoiceStart(() => {
      if (vadMode && !isRecording) {
        startRecording()
      }
    })

    voiceActivation.setOnVoiceEnd(() => {
      if (vadMode && isRecording) {
        stopRecording()
      }
    })
  }, [vadMode, isRecording, startRecording, stopRecording])

  // Set up push-to-talk callbacks
  useEffect(() => {
    pushToTalk.setOnPressStart(() => {
      if (settings.pushToTalk && !isRecording) {
        startRecording()
      }
    })

    pushToTalk.setOnPressEnd(() => {
      if (settings.pushToTalk && isRecording) {
        stopRecording()
      }
    })
  }, [settings.pushToTalk, isRecording, startRecording, stopRecording])

  const toggleRecording = () => {
    if (settings.pushToTalk) {
      addNotification({
        type: 'info',
        message: 'Hold Space bar to record in push-to-talk mode'
      })
      return
    }

    if (isRecording) {
      stopRecording()
    } else {
      startRecording()
    }
  }

  const toggleVadMode = async () => {
    if (!vadMode) {
      const started = await voiceActivation.startListening()
      if (started) {
        setVadMode(true)
        addNotification({
          type: 'success',
          message: 'Voice activation enabled'
        })
      }
    } else {
      voiceActivation.stopListening()
      setVadMode(false)
      addNotification({
        type: 'info',
        message: 'Voice activation disabled'
      })
    }
  }

  // Use VAD audio level if available, otherwise use local audio level
  const displayAudioLevel = vadMode ? voiceActivation.audioLevel : audioLevel
  const isVoiceDetected = vadMode && voiceActivation.isVoiceActive

  // Voice Activity Detection visualization
  const pulseScale = 1 + displayAudioLevel * 0.5
  const ringOpacity = displayAudioLevel * 0.8

  const getRecordingMode = () => {
    if (settings.pushToTalk) return 'push-to-talk'
    if (vadMode) return 'voice-activation'
    return 'manual'
  }

  const getInstructions = () => {
    if (!isInitialized) return "Click Initialize to enable microphone access"
    
    switch (getRecordingMode()) {
      case 'push-to-talk':
        return pushToTalk.isPressed 
          ? "Recording... Release Space to stop"
          : "Hold Space bar to record"
      case 'voice-activation':
        return isVoiceDetected
          ? "Voice detected - Recording..."
          : "Speak to start recording automatically"
      default:
        return "Click to start/stop recording"
    }
  }

  return (
    <div className="flex flex-col items-center space-y-4">
      {/* Recording mode indicators */}
      <div className="flex items-center space-x-2 text-xs">
        {settings.pushToTalk && (
          <div className={cn(
            "flex items-center space-x-1 px-2 py-1 rounded-full",
            pushToTalk.isPressed ? "bg-primary text-primary-foreground" : "bg-muted"
          )}>
            <Hand size={12} />
            <span>Push-to-Talk</span>
          </div>
        )}
        {vadMode && (
          <div className={cn(
            "flex items-center space-x-1 px-2 py-1 rounded-full",
            isVoiceDetected ? "bg-green-500 text-white" : "bg-muted"
          )}>
            <Zap size={12} />
            <span>Voice Activation</span>
          </div>
        )}
      </div>

      {/* Main record button with visualizer */}
      <div className="relative">
        {/* Pulse rings */}
        {(isRecording || isVoiceDetected) && (
          <div 
            className="absolute inset-0 rounded-full border-2 border-primary animate-pulse-ring"
            style={{ 
              opacity: ringOpacity,
              transform: `scale(${pulseScale})`
            }}
          />
        )}
        
        <Button
          size="icon"
          variant={isRecording ? "destructive" : "default"}
          className={cn(
            "h-16 w-16 rounded-full transition-all duration-200",
            (isRecording || isVoiceDetected) && "scale-110",
            pushToTalk.isPressed && "bg-primary scale-110"
          )}
          onClick={toggleRecording}
          disabled={!isInitialized && !mediaRecorder}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
          data-push-to-talk={settings.pushToTalk ? "true" : "false"}
        >
          {isRecording ? (
            <Square size={24} fill="currentColor" />
          ) : settings.pushToTalk && pushToTalk.isPressed ? (
            <Mic size={24} />
          ) : (
            <Mic size={24} />
          )}
        </Button>
      </div>

      {/* Audio level indicator */}
      {(isRecording || vadMode) && (
        <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
          <div 
            className={cn(
              "h-full transition-all duration-100",
              isVoiceDetected ? "bg-green-500" : "bg-primary"
            )}
            style={{ width: `${displayAudioLevel * 100}%` }}
          />
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center space-x-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={initializeAudio}
          disabled={isInitialized}
        >
          {isInitialized ? (
            <Volume2 size={16} className="text-green-500" />
          ) : (
            <VolumeX size={16} className="text-muted-foreground" />
          )}
          <span className="ml-2 text-sm">
            {isInitialized ? 'Ready' : 'Initialize'}
          </span>
        </Button>

        {isInitialized && !settings.pushToTalk && (
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleVadMode}
            className={vadMode ? "text-green-500" : "text-muted-foreground"}
          >
            <Zap size={16} />
            <span className="ml-2 text-sm">
              VAD {vadMode ? 'On' : 'Off'}
            </span>
          </Button>
        )}
      </div>

      {/* Instructions */}
      <p className="text-sm text-muted-foreground text-center max-w-xs">
        {getInstructions()}
      </p>

      {/* Keyboard shortcut hint */}
      {isInitialized && (
        <p className="text-xs text-muted-foreground text-center opacity-75">
          Shortcuts: R (record), Esc (stop), ? (help)
        </p>
      )}
    </div>
  )
}