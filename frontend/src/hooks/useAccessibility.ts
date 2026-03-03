import { useEffect, useState } from 'react'

export function useAccessibility() {
  const [isHighContrast, setIsHighContrast] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [screenReaderActive, setScreenReaderActive] = useState(false)

  useEffect(() => {
    // Check for reduced motion preference
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(motionQuery.matches)
    
    const handleMotionChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches)
    }
    
    motionQuery.addEventListener('change', handleMotionChange)

    // Check for high contrast preference
    const contrastQuery = window.matchMedia('(prefers-contrast: high)')
    setIsHighContrast(contrastQuery.matches)
    
    const handleContrastChange = (e: MediaQueryListEvent) => {
      setIsHighContrast(e.matches)
    }
    
    contrastQuery.addEventListener('change', handleContrastChange)

    // Detect screen reader usage
    const checkScreenReader = () => {
      // Check if any screen reader specific elements are present
      const srOnlyElements = document.querySelectorAll('.sr-only')
      const hasAriaLive = document.querySelectorAll('[aria-live]').length > 0
      const hasAriaLabel = document.querySelectorAll('[aria-label]').length > 0
      
      setScreenReaderActive(srOnlyElements.length > 0 || hasAriaLive || hasAriaLabel)
    }

    // Initial check
    checkScreenReader()
    
    // Check periodically
    const interval = setInterval(checkScreenReader, 5000)

    return () => {
      motionQuery.removeEventListener('change', handleMotionChange)
      contrastQuery.removeEventListener('change', handleContrastChange)
      clearInterval(interval)
    }
  }, [])

  const announceToScreenReader = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const announcement = document.createElement('div')
    announcement.setAttribute('aria-live', priority)
    announcement.setAttribute('aria-atomic', 'true')
    announcement.className = 'sr-only'
    announcement.textContent = message
    
    document.body.appendChild(announcement)
    
    // Remove after announcement
    setTimeout(() => {
      document.body.removeChild(announcement)
    }, 1000)
  }

  const focusElement = (selector: string) => {
    const element = document.querySelector(selector) as HTMLElement
    if (element) {
      element.focus()
      element.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' })
    }
  }

  const skipToContent = () => {
    focusElement('main')
  }

  const skipToNavigation = () => {
    focusElement('nav')
  }

  return {
    isHighContrast,
    reducedMotion,
    screenReaderActive,
    announceToScreenReader,
    focusElement,
    skipToContent,
    skipToNavigation
  }
}