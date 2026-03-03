import { useEffect, useRef } from 'react'
import { useConversationStore } from '@/store/conversationStore'
import { cn } from '@/lib/utils'

export function TranscriptDisplay() {
  const { currentTranscript, isProcessing } = useConversationStore()
  const transcriptRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [currentTranscript])

  if (!currentTranscript && !isProcessing) {
    return null
  }

  return (
    <div className="bg-muted/50 rounded-lg p-4 border border-dashed border-muted-foreground/20">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-muted-foreground">
          Live Transcript
        </h3>
        {isProcessing && (
          <div className="flex items-center space-x-2">
            <div className="animate-spin h-3 w-3 border border-primary border-t-transparent rounded-full" />
            <span className="text-xs text-muted-foreground">Processing...</span>
          </div>
        )}
      </div>
      
      <div
        ref={transcriptRef}
        className={cn(
          "text-sm leading-relaxed min-h-[2rem] transition-opacity duration-200",
          isProcessing && !currentTranscript && "opacity-50"
        )}
      >
        {currentTranscript || (
          <span className="text-muted-foreground italic">
            {isProcessing ? "Listening..." : "Start speaking to see transcript here"}
          </span>
        )}
        {isProcessing && currentTranscript && (
          <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
        )}
      </div>
    </div>
  )
}