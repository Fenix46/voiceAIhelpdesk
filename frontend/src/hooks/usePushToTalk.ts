import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '@/store/appStore'

interface PushToTalkOptions {
  key?: string // Default key to use for push-to-talk
  preventDefault?: boolean
}

export function usePushToTalk(options: PushToTalkOptions = {}) {
  const { key = 'Space', preventDefault = true } = options
  const [isPressed, setIsPressed] = useState(false)
  const [isEnabled, setIsEnabled] = useState(false)
  
  const { settings, addNotification } = useAppStore()

  // Callbacks for push-to-talk events
  const [onPressStart, setOnPressStart] = useState<(() => void) | undefined>()
  const [onPressEnd, setOnPressEnd] = useState<(() => void) | undefined>()

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // Don't trigger in input fields
    if (
      event.target instanceof HTMLInputElement ||
      event.target instanceof HTMLTextAreaElement ||
      event.target instanceof HTMLSelectElement
    ) {
      return
    }

    if (!isEnabled || !settings.pushToTalk) return

    if (event.code === key || event.key === key) {
      if (preventDefault) {
        event.preventDefault()
      }
      
      if (!isPressed) {
        setIsPressed(true)
        onPressStart?.()
      }
    }
  }, [isEnabled, settings.pushToTalk, key, preventDefault, isPressed, onPressStart])

  const handleKeyUp = useCallback((event: KeyboardEvent) => {
    if (!isEnabled || !settings.pushToTalk) return

    if (event.code === key || event.key === key) {
      if (preventDefault) {
        event.preventDefault()
      }
      
      if (isPressed) {
        setIsPressed(false)
        onPressEnd?.()
      }
    }
  }, [isEnabled, settings.pushToTalk, key, preventDefault, isPressed, onPressEnd])

  // Mouse/touch support for mobile
  const handleMouseDown = useCallback((event: MouseEvent | TouchEvent) => {
    if (!isEnabled || !settings.pushToTalk) return
    
    const target = event.target as HTMLElement
    if (target.dataset.pushToTalk === 'true') {
      event.preventDefault()
      setIsPressed(true)
      onPressStart?.()
    }
  }, [isEnabled, settings.pushToTalk, onPressStart])

  const handleMouseUp = useCallback((event: MouseEvent | TouchEvent) => {
    if (!isEnabled || !settings.pushToTalk) return
    
    if (isPressed) {
      event.preventDefault()
      setIsPressed(false)
      onPressEnd?.()
    }
  }, [isEnabled, settings.pushToTalk, isPressed, onPressEnd])

  const enablePushToTalk = useCallback(() => {
    setIsEnabled(true)
    addNotification({
      type: 'info',
      message: `Push-to-talk enabled. Hold ${key} to record.`
    })
  }, [key, addNotification])

  const disablePushToTalk = useCallback(() => {
    setIsEnabled(false)
    setIsPressed(false)
  }, [])

  // Set up event listeners
  useEffect(() => {
    if (!isEnabled) return

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('keyup', handleKeyUp)
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('touchstart', handleMouseDown)
    document.addEventListener('touchend', handleMouseUp)

    // Handle window blur to stop recording if key is held
    const handleBlur = () => {
      if (isPressed) {
        setIsPressed(false)
        onPressEnd?.()
      }
    }
    
    window.addEventListener('blur', handleBlur)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('keyup', handleKeyUp)
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('touchstart', handleMouseDown)
      document.removeEventListener('touchend', handleMouseUp)
      window.removeEventListener('blur', handleBlur)
    }
  }, [isEnabled, handleKeyDown, handleKeyUp, handleMouseDown, handleMouseUp, isPressed, onPressEnd])

  // Auto-enable/disable based on settings
  useEffect(() => {
    if (settings.pushToTalk && !isEnabled) {
      enablePushToTalk()
    } else if (!settings.pushToTalk && isEnabled) {
      disablePushToTalk()
    }
  }, [settings.pushToTalk, isEnabled, enablePushToTalk, disablePushToTalk])

  return {
    isPressed,
    isEnabled,
    enablePushToTalk,
    disablePushToTalk,
    setOnPressStart,
    setOnPressEnd,
    // Configuration
    currentKey: key
  }
}