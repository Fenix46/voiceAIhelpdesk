import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

export interface AppSettings {
  theme: 'light' | 'dark' | 'system'
  pushToTalk: boolean
  noiseReduction: boolean
  autoSave: boolean
  language: string
}

export interface AppState {
  settings: AppSettings
  isOnline: boolean
  notifications: Array<{
    id: string
    type: 'success' | 'error' | 'warning' | 'info'
    message: string
    timestamp: Date
  }>

  // Actions
  updateSettings: (settings: Partial<AppSettings>) => void
  setOnlineStatus: (online: boolean) => void
  addNotification: (notification: Omit<AppState['notifications'][0], 'id' | 'timestamp'>) => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        settings: {
          theme: 'system',
          pushToTalk: false,
          noiseReduction: true,
          autoSave: true,
          language: 'en',
        },
        isOnline: navigator.onLine,
        notifications: [],

        updateSettings: (newSettings) =>
          set((state) => ({
            settings: { ...state.settings, ...newSettings },
          })),

        setOnlineStatus: (online) =>
          set({ isOnline: online }),

        addNotification: (notification) =>
          set((state) => ({
            notifications: [
              ...state.notifications,
              {
                ...notification,
                id: crypto.randomUUID(),
                timestamp: new Date(),
              },
            ],
          })),

        removeNotification: (id) =>
          set((state) => ({
            notifications: state.notifications.filter((n) => n.id !== id),
          })),

        clearNotifications: () =>
          set({ notifications: [] }),
      }),
      {
        name: 'app-store',
        partialize: (state) => ({ settings: state.settings }),
      }
    ),
    { name: 'app-store' }
  )
)