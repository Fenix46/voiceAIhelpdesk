import { useState, useRef, useCallback, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'

interface VoiceActivationOptions {
  threshold?: number // Volume threshold for voice activation (0-1)
  silenceTimeout?: number // Time to wait before stopping (ms)
  minRecordingTime?: number // Minimum recording time (ms)
}

export function useVoiceActivation(options: VoiceActivationOptions = {}) {
  const {
    threshold = 0.1,
    silenceTimeout = 1500,
    minRecordingTime = 1000
  } = options

  const [isVoiceActive, setIsVoiceActive] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [audioLevel, setAudioLevel] = useState(0)
  
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const animationFrameRef = useRef<number>()
  const silenceTimerRef = useRef<NodeJS.Timeout>()
  const recordingStartTimeRef = useRef<number>(0)
  
  const { settings, addNotification } = useAppStore()

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

      audioContextRef.current = new AudioContext()
      const source = audioContextRef.current.createMediaStreamSource(stream)
      analyserRef.current = audioContextRef.current.createAnalyser()
      
      analyserRef.current.fftSize = 256
      analyserRef.current.smoothingTimeConstant = 0.8
      
      source.connect(analyserRef.current)
      mediaStreamRef.current = stream
      
      return true
    } catch (error) {
      console.error('Failed to initialize audio for VAD:', error)
      addNotification({
        type: 'error',
        message: 'Failed to access microphone for voice activation'
      })
      return false
    }
  }, [settings.noiseReduction, addNotification])

  const analyzeAudio = useCallback(() => {
    if (!analyserRef.current) return

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(dataArray)
    
    // Calculate RMS (Root Mean Square) for better voice detection
    const rms = Math.sqrt(
      dataArray.reduce((sum, value) => sum + value * value, 0) / dataArray.length
    ) / 255

    setAudioLevel(rms)

    const isVoiceDetected = rms > threshold

    if (isVoiceDetected) {
      if (!isVoiceActive) {
        setIsVoiceActive(true)
        recordingStartTimeRef.current = Date.now()
        onVoiceStart?.()
      }
      
      // Clear any existing silence timer
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current)
        silenceTimerRef.current = undefined
      }
    } else if (isVoiceActive) {
      // Start silence timer if not already running
      if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          const recordingDuration = Date.now() - recordingStartTimeRef.current
          
          // Only stop if we've been recording for minimum time
          if (recordingDuration >= minRecordingTime) {
            setIsVoiceActive(false)
            onVoiceEnd?.()
          }
          
          silenceTimerRef.current = undefined
        }, silenceTimeout)
      }
    }

    if (isListening) {
      animationFrameRef.current = requestAnimationFrame(analyzeAudio)
    }
  }, [isVoiceActive, isListening, threshold, silenceTimeout, minRecordingTime])

  const startListening = useCallback(async () => {
    if (isListening) return false

    const initialized = await initializeAudio()
    if (!initialized) return false

    setIsListening(true)
    analyzeAudio()
    return true
  }, [isListening, initializeAudio, analyzeAudio])

  const stopListening = useCallback(() => {
    setIsListening(false)
    setIsVoiceActive(false)
    setAudioLevel(0)

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = undefined
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    analyserRef.current = null
  }, [])

  // Callbacks for voice activation events
  const [onVoiceStart, setOnVoiceStart] = useState<(() => void) | undefined>()
  const [onVoiceEnd, setOnVoiceEnd] = useState<(() => void) | undefined>()

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening()
    }
  }, [stopListening])

  return {
    isVoiceActive,
    isListening,
    audioLevel,
    startListening,
    stopListening,
    setOnVoiceStart,
    setOnVoiceEnd,
    // Voice activation configuration
    threshold,
    silenceTimeout,
    minRecordingTime
  }
}