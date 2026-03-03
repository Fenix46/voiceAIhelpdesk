import { useState, useRef, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Upload,
  File,
  X,
  Play,
  Pause,
  Volume2,
  Clock,
  FileAudio,
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  Download,
  Trash2,
  Settings,
  Mic,
  Square,
  RotateCcw,
  Zap
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface AudioFile {
  id: string
  file: File
  name: string
  size: number
  duration?: number
  url: string
  type: string
  uploadProgress: number
  processingStatus: 'idle' | 'uploading' | 'processing' | 'completed' | 'error'
  transcription?: string
  analysis?: {
    sampleRate: number
    channels: number
    bitDepth: number
    codec: string
    quality: 'low' | 'medium' | 'high'
    noiseLevel: number
    speechDetected: boolean
    languageDetected?: string
    confidence?: number
  }
  error?: string
  metadata?: Record<string, any>
}

interface AudioUploaderProps {
  onFileUpload?: (files: AudioFile[]) => void
  onFileProcess?: (fileId: string) => Promise<void>
  onFileDelete?: (fileId: string) => void
  onTranscribe?: (fileId: string) => Promise<string>
  maxFiles?: number
  maxFileSize?: number // in bytes
  acceptedFormats?: string[]
  showAnalysis?: boolean
  showTranscription?: boolean
  enableRecording?: boolean
  className?: string
}

export function AudioUploader({
  onFileUpload,
  onFileProcess,
  onFileDelete,
  onTranscribe,
  maxFiles = 10,
  maxFileSize = 100 * 1024 * 1024, // 100MB
  acceptedFormats = ['.wav', '.mp3', '.m4a', '.ogg', '.flac'],
  showAnalysis = true,
  showTranscription = true,
  enableRecording = true,
  className
}: AudioUploaderProps) {
  const [audioFiles, setAudioFiles] = useState<AudioFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [playingFile, setPlayingFile] = useState<string | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [recordingDuration, setRecordingDuration] = useState(0)
  
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null)

  // File drop zone
  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    // Handle rejected files
    if (rejectedFiles.length > 0) {
      console.warn('Some files were rejected:', rejectedFiles)
    }

    // Process accepted files
    const newAudioFiles: AudioFile[] = acceptedFiles.map(file => {
      const url = URL.createObjectURL(file)
      return {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        name: file.name,
        size: file.size,
        url,
        type: file.type,
        uploadProgress: 0,
        processingStatus: 'idle'
      }
    })

    setAudioFiles(prev => [...prev, ...newAudioFiles].slice(0, maxFiles))
    
    // Start processing files
    newAudioFiles.forEach(audioFile => {
      processAudioFile(audioFile)
    })

    onFileUpload?.(newAudioFiles)
  }, [maxFiles, onFileUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': acceptedFormats
    },
    maxFiles: maxFiles - audioFiles.length,
    maxSize: maxFileSize,
    disabled: audioFiles.length >= maxFiles
  })

  const processAudioFile = async (audioFile: AudioFile) => {
    try {
      // Update status to processing
      updateFileStatus(audioFile.id, 'processing')

      // Simulate file processing
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Get audio metadata
      const audio = new Audio(audioFile.url)
      await new Promise((resolve, reject) => {
        audio.addEventListener('loadedmetadata', resolve)
        audio.addEventListener('error', reject)
        audio.load()
      })

      const analysis = {
        sampleRate: 44100, // This would come from actual audio analysis
        channels: 2,
        bitDepth: 16,
        codec: audioFile.type.split('/')[1] || 'unknown',
        quality: audioFile.size > 10 * 1024 * 1024 ? 'high' : 
                audioFile.size > 5 * 1024 * 1024 ? 'medium' : 'low',
        noiseLevel: Math.random() * 0.3, // Simulated
        speechDetected: Math.random() > 0.2,
        languageDetected: 'en-US',
        confidence: 0.8 + Math.random() * 0.2
      } as const

      // Update file with analysis
      setAudioFiles(prev => prev.map(f => 
        f.id === audioFile.id 
          ? { 
              ...f, 
              duration: audio.duration,
              analysis,
              processingStatus: 'completed' as const,
              uploadProgress: 100
            }
          : f
      ))

      // Process with external handler if provided
      if (onFileProcess) {
        await onFileProcess(audioFile.id)
      }

    } catch (error) {
      console.error('Error processing audio file:', error)
      updateFileStatus(audioFile.id, 'error', error instanceof Error ? error.message : 'Unknown error')
    }
  }

  const updateFileStatus = (fileId: string, status: AudioFile['processingStatus'], error?: string) => {
    setAudioFiles(prev => prev.map(f => 
      f.id === fileId 
        ? { ...f, processingStatus: status, error }
        : f
    ))
  }

  const deleteFile = (fileId: string) => {
    const file = audioFiles.find(f => f.id === fileId)
    if (file) {
      URL.revokeObjectURL(file.url)
      setAudioFiles(prev => prev.filter(f => f.id !== fileId))
      if (selectedFile === fileId) setSelectedFile(null)
      if (playingFile === fileId) setPlayingFile(null)
      onFileDelete?.(fileId)
    }
  }

  const playAudio = async (fileId: string) => {
    const file = audioFiles.find(f => f.id === fileId)
    if (!file || !audioRef.current) return

    try {
      if (playingFile === fileId) {
        audioRef.current.pause()
        setPlayingFile(null)
      } else {
        audioRef.current.src = file.url
        await audioRef.current.play()
        setPlayingFile(fileId)
        
        audioRef.current.onended = () => setPlayingFile(null)
      }
    } catch (error) {
      console.error('Error playing audio:', error)
    }
  }

  const transcribeFile = async (fileId: string) => {
    if (!onTranscribe) return

    try {
      updateFileStatus(fileId, 'processing')
      const transcription = await onTranscribe(fileId)
      
      setAudioFiles(prev => prev.map(f => 
        f.id === fileId 
          ? { ...f, transcription, processingStatus: 'completed' }
          : f
      ))
    } catch (error) {
      console.error('Error transcribing audio:', error)
      updateFileStatus(fileId, 'error', 'Transcription failed')
    }
  }

  // Recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorderRef.current = new MediaRecorder(stream)
      
      const chunks: BlobPart[] = []
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        chunks.push(event.data)
      }
      
      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/wav' })
        const file = new File([blob], `recording-${Date.now()}.wav`, { type: 'audio/wav' })
        onDrop([file], [])
        
        // Clean up
        stream.getTracks().forEach(track => track.stop())
        setRecordingDuration(0)
        if (recordingTimerRef.current) {
          clearInterval(recordingTimerRef.current)
        }
      }
      
      mediaRecorderRef.current.start()
      setIsRecording(true)
      
      // Start timer
      recordingTimerRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 1)
      }, 1000)
      
    } catch (error) {
      console.error('Error starting recording:', error)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getStatusIcon = (status: AudioFile['processingStatus']) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return <Loader2 size={16} className="animate-spin text-blue-500" />
      case 'completed':
        return <CheckCircle size={16} className="text-green-500" />
      case 'error':
        return <AlertCircle size={16} className="text-red-500" />
      default:
        return <FileAudio size={16} className="text-muted-foreground" />
    }
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg flex items-center space-x-2">
            <Upload size={20} className="text-primary" />
            <span>Audio Uploader</span>
          </h3>
          <p className="text-sm text-muted-foreground">
            Upload audio files for testing and analysis
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">
            {audioFiles.length}/{maxFiles} files
          </span>
          
          {enableRecording && (
            <Button
              size="sm"
              variant={isRecording ? "destructive" : "outline"}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={audioFiles.length >= maxFiles}
            >
              {isRecording ? (
                <>
                  <Square size={14} className="mr-1" />
                  Stop ({formatDuration(recordingDuration)})
                </>
              ) : (
                <>
                  <Mic size={14} className="mr-1" />
                  Record
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          isDragActive 
            ? "border-primary bg-primary/5" 
            : "border-muted-foreground/25 hover:border-primary/50",
          audioFiles.length >= maxFiles && "opacity-50 cursor-not-allowed"
        )}
      >
        <input {...getInputProps()} />
        <Upload size={48} className="mx-auto mb-4 text-muted-foreground" />
        
        {isDragActive ? (
          <p className="text-lg font-medium">Drop the audio files here...</p>
        ) : (
          <div>
            <p className="text-lg font-medium mb-2">
              Drag & drop audio files here, or click to select
            </p>
            <p className="text-sm text-muted-foreground">
              Supports {acceptedFormats.join(', ')} up to {formatFileSize(maxFileSize)}
            </p>
          </div>
        )}
      </div>

      {/* File List */}
      {audioFiles.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-medium">Uploaded Files</h4>
          
          <div className="space-y-2">
            <AnimatePresence>
              {audioFiles.map((file) => (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -100 }}
                  className={cn(
                    "p-4 border rounded-lg transition-colors cursor-pointer",
                    selectedFile === file.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  )}
                  onClick={() => setSelectedFile(selectedFile === file.id ? null : file.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="flex-shrink-0">
                        {getStatusIcon(file.processingStatus)}
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <h5 className="font-medium truncate">{file.name}</h5>
                        <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                          <span>{formatFileSize(file.size)}</span>
                          {file.duration && <span>{formatDuration(file.duration)}</span>}
                          <span className="capitalize">{file.processingStatus}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      {file.processingStatus === 'completed' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation()
                            playAudio(file.id)
                          }}
                        >
                          {playingFile === file.id ? (
                            <Pause size={12} />
                          ) : (
                            <Play size={12} />
                          )}
                        </Button>
                      )}
                      
                      {showTranscription && file.processingStatus === 'completed' && !file.transcription && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation()
                            transcribeFile(file.id)
                          }}
                        >
                          <Zap size={12} className="mr-1" />
                          Transcribe
                        </Button>
                      )}
                      
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteFile(file.id)
                        }}
                      >
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  </div>

                  {/* Processing Progress */}
                  {file.processingStatus === 'processing' && (
                    <div className="mt-3">
                      <div className="w-full bg-muted rounded-full h-1">
                        <div 
                          className="h-1 bg-primary rounded-full transition-all duration-300"
                          style={{ width: `${file.uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Error Message */}
                  {file.error && (
                    <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 dark:bg-red-900/10 dark:border-red-800 dark:text-red-300">
                      {file.error}
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* File Details */}
      {selectedFile && (
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="p-4 bg-muted/20 rounded-lg"
          >
            {(() => {
              const file = audioFiles.find(f => f.id === selectedFile)
              if (!file) return null
              
              return (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">File Details</h4>
                    <div className="flex space-x-2">
                      <Button size="sm" variant="outline">
                        <Download size={14} className="mr-1" />
                        Download
                      </Button>
                      <Button size="sm" variant="outline">
                        <Settings size={14} className="mr-1" />
                        Settings
                      </Button>
                    </div>
                  </div>
                  
                  {/* Basic Info */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Name:</span>
                      <div className="font-medium truncate">{file.name}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Size:</span>
                      <div className="font-medium">{formatFileSize(file.size)}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Type:</span>
                      <div className="font-medium">{file.type}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Duration:</span>
                      <div className="font-medium">
                        {file.duration ? formatDuration(file.duration) : 'Unknown'}
                      </div>
                    </div>
                  </div>

                  {/* Audio Analysis */}
                  {showAnalysis && file.analysis && (
                    <div>
                      <h5 className="font-medium mb-3">Audio Analysis</h5>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Sample Rate:</span>
                          <div className="font-medium">{file.analysis.sampleRate} Hz</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Channels:</span>
                          <div className="font-medium">{file.analysis.channels}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Quality:</span>
                          <div className={cn(
                            "font-medium capitalize",
                            file.analysis.quality === 'high' ? 'text-green-600' :
                            file.analysis.quality === 'medium' ? 'text-yellow-600' : 'text-red-600'
                          )}>
                            {file.analysis.quality}
                          </div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Speech Detected:</span>
                          <div className={cn(
                            "font-medium",
                            file.analysis.speechDetected ? 'text-green-600' : 'text-red-600'
                          )}>
                            {file.analysis.speechDetected ? 'Yes' : 'No'}
                          </div>
                        </div>
                      </div>

                      {/* Noise Level Indicator */}
                      <div className="mt-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-muted-foreground">Noise Level</span>
                          <span className="text-sm font-medium">
                            {(file.analysis.noiseLevel * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div 
                            className={cn(
                              "h-2 rounded-full transition-all",
                              file.analysis.noiseLevel > 0.5 ? 'bg-red-500' :
                              file.analysis.noiseLevel > 0.3 ? 'bg-yellow-500' : 'bg-green-500'
                            )}
                            style={{ width: `${file.analysis.noiseLevel * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Transcription */}
                  {showTranscription && file.transcription && (
                    <div>
                      <h5 className="font-medium mb-2">Transcription</h5>
                      <div className="p-3 bg-background border rounded text-sm">
                        {file.transcription}
                      </div>
                    </div>
                  )}
                </div>
              )
            })()}
          </motion.div>
        </AnimatePresence>
      )}

      {/* Bulk Actions */}
      {audioFiles.length > 1 && (
        <div className="flex items-center justify-between p-3 bg-muted/20 rounded-lg">
          <span className="text-sm text-muted-foreground">
            {audioFiles.filter(f => f.processingStatus === 'completed').length} of {audioFiles.length} processed
          </span>
          <div className="flex space-x-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                audioFiles.forEach(file => {
                  if (file.processingStatus === 'completed' && !file.transcription) {
                    transcribeFile(file.id)
                  }
                })
              }}
              disabled={!showTranscription || !audioFiles.some(f => f.processingStatus === 'completed' && !f.transcription)}
            >
              <Zap size={14} className="mr-1" />
              Transcribe All
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setAudioFiles([])
                setSelectedFile(null)
                setPlayingFile(null)
              }}
            >
              <Trash2 size={14} className="mr-1" />
              Clear All
            </Button>
          </div>
        </div>
      )}

      <audio ref={audioRef} />
    </div>
  )
}