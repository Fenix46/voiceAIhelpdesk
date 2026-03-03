import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useAppStore } from '@/store/appStore'
import { useTheme } from '@/providers/ThemeProvider'
import { 
  Settings,
  Mic,
  Volume2,
  Moon,
  Sun,
  Monitor,
  Save,
  RotateCcw,
  Bell,
  Shield,
  Database,
  Wifi,
  Download,
  Upload,
  Trash2
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function SettingsPage() {
  const { settings, updateSettings, addNotification } = useAppStore()
  const { theme, setTheme } = useTheme()
  const [tempSettings, setTempSettings] = useState(settings)
  const [hasChanges, setHasChanges] = useState(false)

  const handleSettingChange = (key: keyof typeof settings, value: any) => {
    setTempSettings(prev => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const handleSave = () => {
    updateSettings(tempSettings)
    setHasChanges(false)
    addNotification({
      type: 'success',
      message: 'Settings saved successfully'
    })
  }

  const handleReset = () => {
    const defaultSettings = {
      theme: 'system' as const,
      pushToTalk: false,
      noiseReduction: true,
      autoSave: true,
      language: 'en',
    }
    setTempSettings(defaultSettings)
    setHasChanges(true)
  }

  const handleExportSettings = () => {
    const exportData = {
      settings: tempSettings,
      exportedAt: new Date().toISOString(),
      version: '1.0'
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'voicehelpdesk-settings.json'
    a.click()
    URL.revokeObjectURL(url)
    
    addNotification({
      type: 'success',
      message: 'Settings exported successfully'
    })
  }

  const handleImportSettings = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const importData = JSON.parse(e.target?.result as string)
        if (importData.settings) {
          setTempSettings(importData.settings)
          setHasChanges(true)
          addNotification({
            type: 'success',
            message: 'Settings imported successfully'
          })
        }
      } catch (error) {
        addNotification({
          type: 'error',
          message: 'Failed to import settings'
        })
      }
    }
    reader.readAsText(file)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">
            Configure your VoiceHelpDesk experience
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportSettings}
          >
            <Download size={16} className="mr-2" />
            Export
          </Button>
          
          <label>
            <Button
              variant="outline"
              size="sm"
              asChild
            >
              <span>
                <Upload size={16} className="mr-2" />
                Import
              </span>
            </Button>
            <input
              type="file"
              accept=".json"
              onChange={handleImportSettings}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {/* Save Actions */}
      {hasChanges && (
        <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Settings size={16} className="text-blue-600 dark:text-blue-400" />
              <span className="font-medium text-blue-800 dark:text-blue-200">
                You have unsaved changes
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setTempSettings(settings)
                  setHasChanges(false)
                }}
              >
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave}>
                <Save size={16} className="mr-2" />
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Appearance Settings */}
        <div className="space-y-6">
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center space-x-2 mb-4">
              <Monitor size={20} className="text-primary" />
              <h2 className="text-xl font-semibold">Appearance</h2>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Theme</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { value: 'light', label: 'Light', icon: Sun },
                    { value: 'dark', label: 'Dark', icon: Moon },
                    { value: 'system', label: 'System', icon: Monitor }
                  ].map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      onClick={() => {
                        setTheme(value as any)
                        handleSettingChange('theme', value)
                      }}
                      className={cn(
                        "flex flex-col items-center p-3 rounded-lg border transition-colors",
                        theme === value
                          ? "border-primary bg-primary/10"
                          : "border-muted hover:bg-muted/50"
                      )}
                    >
                      <Icon size={20} className="mb-1" />
                      <span className="text-sm">{label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Language</label>
                <select
                  value={tempSettings.language}
                  onChange={(e) => handleSettingChange('language', e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="de">Deutsch</option>
                  <option value="it">Italiano</option>
                </select>
              </div>
            </div>
          </div>

          {/* Audio Settings */}
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center space-x-2 mb-4">
              <Mic size={20} className="text-primary" />
              <h2 className="text-xl font-semibold">Audio</h2>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">Push to Talk</label>
                  <p className="text-xs text-muted-foreground">
                    Hold to record, release to stop
                  </p>
                </div>
                <button
                  onClick={() => handleSettingChange('pushToTalk', !tempSettings.pushToTalk)}
                  className={cn(
                    "w-10 h-6 rounded-full transition-colors relative",
                    tempSettings.pushToTalk ? "bg-primary" : "bg-muted"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 rounded-full bg-white transition-transform absolute top-1",
                    tempSettings.pushToTalk ? "translate-x-5" : "translate-x-1"
                  )} />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">Noise Reduction</label>
                  <p className="text-xs text-muted-foreground">
                    Filter background noise
                  </p>
                </div>
                <button
                  onClick={() => handleSettingChange('noiseReduction', !tempSettings.noiseReduction)}
                  className={cn(
                    "w-10 h-6 rounded-full transition-colors relative",
                    tempSettings.noiseReduction ? "bg-primary" : "bg-muted"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 rounded-full bg-white transition-transform absolute top-1",
                    tempSettings.noiseReduction ? "translate-x-5" : "translate-x-1"
                  )} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* System Settings */}
        <div className="space-y-6">
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center space-x-2 mb-4">
              <Database size={20} className="text-primary" />
              <h2 className="text-xl font-semibold">Data & Storage</h2>
            </div>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-sm font-medium">Auto Save</label>
                  <p className="text-xs text-muted-foreground">
                    Automatically save conversations
                  </p>
                </div>
                <button
                  onClick={() => handleSettingChange('autoSave', !tempSettings.autoSave)}
                  className={cn(
                    "w-10 h-6 rounded-full transition-colors relative",
                    tempSettings.autoSave ? "bg-primary" : "bg-muted"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 rounded-full bg-white transition-transform absolute top-1",
                    tempSettings.autoSave ? "translate-x-5" : "translate-x-1"
                  )} />
                </button>
              </div>

              <div className="p-3 bg-muted rounded-lg">
                <h3 className="font-medium mb-2">Storage Usage</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Conversations:</span>
                    <span>2.3 MB</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Audio Files:</span>
                    <span>15.7 MB</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Settings:</span>
                    <span>0.1 MB</span>
                  </div>
                  <div className="border-t pt-2 font-medium">
                    <div className="flex justify-between">
                      <span>Total:</span>
                      <span>18.1 MB</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Privacy & Security */}
          <div className="bg-card border rounded-lg p-6">
            <div className="flex items-center space-x-2 mb-4">
              <Shield size={20} className="text-primary" />
              <h2 className="text-xl font-semibold">Privacy & Security</h2>
            </div>
            
            <div className="space-y-4">
              <div className="p-3 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg">
                <div className="flex items-center space-x-2 mb-2">
                  <Shield size={16} className="text-green-600 dark:text-green-400" />
                  <span className="font-medium text-green-800 dark:text-green-200">
                    Data Protection
                  </span>
                </div>
                <ul className="text-sm text-green-700 dark:text-green-300 space-y-1">
                  <li>• All audio data is encrypted in transit</li>
                  <li>• Conversations are stored locally</li>
                  <li>• No personal data is shared with third parties</li>
                  <li>• You can delete your data at any time</li>
                </ul>
              </div>

              <Button variant="outline" className="w-full text-destructive hover:text-destructive">
                <Trash2 size={16} className="mr-2" />
                Clear All Data
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* System Information */}
      <div className="bg-card border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">System Information</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
          <div>
            <h3 className="font-medium mb-2">Application</h3>
            <div className="space-y-1 text-muted-foreground">
              <div>Version: 1.0.0</div>
              <div>Build: 2024.1.1</div>
              <div>Environment: Production</div>
            </div>
          </div>
          <div>
            <h3 className="font-medium mb-2">Browser</h3>
            <div className="space-y-1 text-muted-foreground">
              <div>User Agent: {navigator.userAgent.split(' ').slice(0, 3).join(' ')}</div>
              <div>Language: {navigator.language}</div>
              <div>Platform: {navigator.platform}</div>
            </div>
          </div>
          <div>
            <h3 className="font-medium mb-2">Connection</h3>
            <div className="space-y-1 text-muted-foreground">
              <div className="flex items-center space-x-2">
                <Wifi size={14} className="text-green-500" />
                <span>Online</span>
              </div>
              <div>WebSocket: Connected</div>
              <div>Last Sync: Just now</div>
            </div>
          </div>
        </div>
      </div>

      {/* Reset Section */}
      <div className="bg-card border rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold mb-2">Reset Settings</h2>
            <p className="text-muted-foreground text-sm">
              Restore all settings to their default values. This action cannot be undone.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={handleReset}
            className="text-destructive hover:text-destructive"
          >
            <RotateCcw size={16} className="mr-2" />
            Reset to Defaults
          </Button>
        </div>
      </div>
    </div>
  )
}