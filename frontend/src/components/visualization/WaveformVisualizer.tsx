import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface WaveformVisualizerProps {
  audioData?: Float32Array
  isRecording: boolean
  isPlaying?: boolean
  height?: number
  className?: string
  showFrequency?: boolean
  color?: string
}

export function WaveformVisualizer({
  audioData,
  isRecording,
  isPlaying = false,
  height = 100,
  className,
  showFrequency = false,
  color = '#3b82f6'
}: WaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameRef = useRef<number>()
  const [audioContext, setAudioContext] = useState<AudioContext | null>(null)
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null)

  useEffect(() => {
    if (!isRecording && !isPlaying) return

    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const draw = () => {
      const { width, height: canvasHeight } = canvas
      
      // Clear canvas
      ctx.fillStyle = 'transparent'
      ctx.clearRect(0, 0, width, canvasHeight)

      if (audioData && audioData.length > 0) {
        // Draw waveform
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.beginPath()

        const sliceWidth = width / audioData.length
        let x = 0

        for (let i = 0; i < audioData.length; i++) {
          const v = audioData[i] * 0.5 // Normalize
          const y = (v * canvasHeight) / 2 + canvasHeight / 2

          if (i === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }

          x += sliceWidth
        }

        ctx.stroke()

        // Add glow effect if recording
        if (isRecording) {
          ctx.shadowColor = color
          ctx.shadowBlur = 10
          ctx.stroke()
          ctx.shadowBlur = 0
        }
      } else if (isRecording) {
        // Show animated bars when recording but no data
        const numBars = 50
        const barWidth = width / numBars
        const time = Date.now() * 0.01

        ctx.fillStyle = color

        for (let i = 0; i < numBars; i++) {
          const amplitude = Math.sin(time + i * 0.5) * 0.3 + 0.1
          const barHeight = amplitude * canvasHeight
          const x = i * barWidth
          const y = (canvasHeight - barHeight) / 2

          ctx.fillRect(x, y, barWidth - 1, barHeight)
        }
      }

      // Frequency visualization
      if (showFrequency && analyser) {
        const freqData = new Uint8Array(analyser.frequencyBinCount)
        analyser.getByteFrequencyData(freqData)

        ctx.fillStyle = `${color}40` // Semi-transparent
        const barWidth = width / freqData.length
        
        for (let i = 0; i < freqData.length; i++) {
          const barHeight = (freqData[i] / 255) * canvasHeight * 0.8
          const x = i * barWidth
          const y = canvasHeight - barHeight

          ctx.fillRect(x, y, barWidth - 1, barHeight)
        }
      }

      animationFrameRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [audioData, isRecording, isPlaying, color, showFrequency, analyser])

  // Initialize audio context for frequency analysis
  useEffect(() => {
    if (showFrequency && !audioContext) {
      const ctx = new AudioContext()
      const analyserNode = ctx.createAnalyser()
      analyserNode.fftSize = 256
      
      setAudioContext(ctx)
      setAnalyser(analyserNode)
    }

    return () => {
      if (audioContext) {
        audioContext.close()
      }
    }
  }, [showFrequency, audioContext])

  // Handle canvas resize
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const resizeCanvas = () => {
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * window.devicePixelRatio
      canvas.height = height * window.devicePixelRatio
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${height}px`
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
      }
    }

    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    return () => window.removeEventListener('resize', resizeCanvas)
  }, [height])

  return (
    <div className={cn("relative", className)}>
      <canvas
        ref={canvasRef}
        className="w-full rounded-md bg-muted/20"
        style={{ height }}
      />
      
      {/* Recording indicator */}
      {isRecording && (
        <div className="absolute top-2 right-2 flex items-center space-x-1 text-xs">
          <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          <span className="text-red-500 font-medium">REC</span>
        </div>
      )}

      {/* Level indicator */}
      {audioData && (
        <div className="absolute bottom-2 left-2 text-xs text-muted-foreground">
          Level: {Math.round((audioData.reduce((a, b) => a + Math.abs(b), 0) / audioData.length) * 100)}%
        </div>
      )}
    </div>
  )
}