import { useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNetworkStore } from '@/store/networkStore'

export default function NetworkBanner() {
  const { isOffline, setIsOffline } = useNetworkStore()
  const queryClient = useQueryClient()

  useEffect(() => {
    const handleOnline = () => {
      // Re-check with ping
      fetch('/api/health')
        .then((res) => {
          if (res.ok) {
            setIsOffline(false)
            queryClient.invalidateQueries()
          }
        })
        .catch(() => {})
    }

    const handleOffline = () => {
      setIsOffline(true)
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [setIsOffline, queryClient])

  // Periodic retry when offline
  useEffect(() => {
    if (!isOffline) return

    const interval = setInterval(() => {
      fetch('/api/health')
        .then((res) => {
          if (res.ok) {
            setIsOffline(false)
            queryClient.invalidateQueries()
          }
        })
        .catch(() => {
          // Still offline, will retry
        })
    }, 3000)

    return () => clearInterval(interval)
  }, [isOffline, setIsOffline, queryClient])

  if (!isOffline) return null

  return (
    <div
      className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-xs text-amber-700 dark:text-amber-300 font-medium text-center flex items-center justify-center gap-2 z-50 shrink-0"
      data-testid="network-banner"
    >
      <Loader2 className="h-3 w-3 animate-spin text-amber-600 dark:text-amber-400" />
      <span>Can't reach the server. Retrying…</span>
    </div>
  )
}
