import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
  audioUrl?: string
}

export interface ConversationState {
  messages: Message[]
  currentTranscript: string
  isRecording: boolean
  isProcessing: boolean
  sessionId: string | null
  
  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void
  updateTranscript: (transcript: string) => void
  setRecording: (recording: boolean) => void
  setProcessing: (processing: boolean) => void
  setSessionId: (sessionId: string) => void
  clearConversation: () => void
}

export const useConversationStore = create<ConversationState>()(
  devtools(
    (set, get) => ({
      messages: [],
      currentTranscript: '',
      isRecording: false,
      isProcessing: false,
      sessionId: null,

      addMessage: (message) =>
        set((state) => ({
          messages: [
            ...state.messages,
            {
              ...message,
              id: crypto.randomUUID(),
              timestamp: new Date(),
            },
          ],
        })),

      updateTranscript: (transcript) =>
        set({ currentTranscript: transcript }),

      setRecording: (recording) =>
        set({ isRecording: recording }),

      setProcessing: (processing) =>
        set({ isProcessing: processing }),

      setSessionId: (sessionId) =>
        set({ sessionId }),

      clearConversation: () =>
        set({
          messages: [],
          currentTranscript: '',
          sessionId: null,
        }),
    }),
    { name: 'conversation-store' }
  )
)