import { useLoading } from '@/hooks/useLoading'
import { Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LoadingOverlayProps {
  loadingKey?: string
  showProgress?: boolean
  className?: string
}

export function LoadingOverlay({ loadingKey, showProgress = false, className }: LoadingOverlayProps) {
  const { loadingStates, isAnyLoading } = useLoading()

  // If a specific key is provided, use that state, otherwise check if any loading
  const isLoading = loadingKey ? loadingStates[loadingKey]?.isLoading : isAnyLoading()
  const error = loadingKey ? loadingStates[loadingKey]?.error : null
  const progress = loadingKey ? loadingStates[loadingKey]?.progress : undefined

  if (!isLoading && !error) return null

  return (
    <div className={cn(
      "fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center",
      className
    )}>
      <div className="bg-card border rounded-lg p-6 shadow-lg max-w-sm w-full mx-4">
        {error ? (
          <div className="text-center space-y-4">
            <AlertCircle size={48} className="mx-auto text-destructive" />
            <div>
              <h3 className="font-semibold text-lg mb-2">Error</h3>
              <p className="text-sm text-muted-foreground">{error.message}</p>
            </div>
          </div>
        ) : (
          <div className="text-center space-y-4">
            <Loader2 size={48} className="mx-auto animate-spin text-primary" />
            <div>
              <h3 className="font-semibold text-lg mb-2">Loading...</h3>
              <p className="text-sm text-muted-foreground">
                Please wait while we process your request
              </p>
            </div>
            
            {showProgress && progress !== undefined && (
              <div className="space-y-2">
                <div className="w-full bg-muted rounded-full h-2">
                  <div 
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {Math.round(progress)}% complete
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface InlineLoadingProps {
  loadingKey: string
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  className?: string
}

export function InlineLoading({ loadingKey, size = 'md', showText = true, className }: InlineLoadingProps) {
  const { getLoadingState } = useLoading()
  const { isLoading, error, progress } = getLoadingState(loadingKey)

  if (!isLoading && !error) return null

  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8'
  }

  return (
    <div className={cn("flex items-center space-x-2", className)}>
      {error ? (
        <>
          <AlertCircle size={size === 'sm' ? 16 : size === 'md' ? 24 : 32} className="text-destructive" />
          {showText && (
            <span className="text-sm text-destructive">{error.message}</span>
          )}
        </>
      ) : (
        <>
          <Loader2 className={cn("animate-spin text-primary", sizeClasses[size])} />
          {showText && (
            <span className="text-sm text-muted-foreground">
              {progress !== undefined ? `Loading... ${Math.round(progress)}%` : 'Loading...'}
            </span>
          )}
        </>
      )}
    </div>
  )
}

interface LoadingButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loadingKey: string
  children: React.ReactNode
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
}

export function LoadingButton({ 
  loadingKey, 
  children, 
  disabled, 
  className,
  ...props 
}: LoadingButtonProps) {
  const { getLoadingState } = useLoading()
  const { isLoading } = getLoadingState(loadingKey)

  return (
    <button
      {...props}
      disabled={disabled || isLoading}
      className={cn(
        "inline-flex items-center justify-center gap-2",
        className
      )}
    >
      {isLoading && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  )
}