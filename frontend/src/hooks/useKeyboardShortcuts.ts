import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useConversationStore } from '@/store/conversationStore'
import { useAppStore } from '@/store/appStore'

export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const { isRecording, clearConversation } = useConversationStore()
  const { addNotification } = useAppStore()

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      ) {
        return
      }

      // Ctrl/Cmd + key combinations
      if (event.ctrlKey || event.metaKey) {
        switch (event.key.toLowerCase()) {
          case 'k':
            event.preventDefault()
            // Focus search or open command palette
            addNotification({
              type: 'info',
              message: 'Command palette coming soon!'
            })
            break
          
          case 'n':
            event.preventDefault()
            navigate('/conversation')
            addNotification({
              type: 'info',
              message: 'Starting new conversation'
            })
            break
          
          case 'd':
            event.preventDefault()
            navigate('/dashboard')
            break
          
          case 't':
            event.preventDefault()
            navigate('/tickets')
            break
          
          case ',':
            event.preventDefault()
            navigate('/settings')
            break
          
          case 'h':
            event.preventDefault()
            navigate('/')
            break
        }
      }

      // Single key shortcuts
      switch (event.key.toLowerCase()) {
        case 'r':
          if (!isRecording && window.location.pathname === '/conversation') {
            event.preventDefault()
            // Trigger recording start
            const recordButton = document.querySelector('[aria-label*="recording"]') as HTMLButtonElement
            recordButton?.click()
          }
          break
        
        case 'escape':
          if (isRecording) {
            event.preventDefault()
            // Stop recording
            const recordButton = document.querySelector('[aria-label*="recording"]') as HTMLButtonElement
            recordButton?.click()
          }
          break
        
        case '?':
          event.preventDefault()
          showShortcutsHelp()
          break
      }

      // Shift + key combinations
      if (event.shiftKey) {
        switch (event.key.toLowerCase()) {
          case 'c':
            if (window.location.pathname === '/conversation') {
              event.preventDefault()
              if (window.confirm('Clear conversation?')) {
                clearConversation()
                addNotification({
                  type: 'info',
                  message: 'Conversation cleared'
                })
              }
            }
            break
        }
      }
    }

    const showShortcutsHelp = () => {
      addNotification({
        type: 'info',
        message: 'Keyboard shortcuts: Ctrl+N (new), R (record), Esc (stop), ? (help)'
      })
    }

    document.addEventListener('keydown', handleKeyDown)
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [navigate, isRecording, clearConversation, addNotification])
}