import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { Skeleton } from '@/components/ui/skeleton'

/** Fetches /api/auth/me once and populates the auth store. */
export function AuthProvider() {
  const { setUser, setChecked, checked } = useAuthStore()

  useEffect(() => {
    api.get<{ id: number; email: string; name: string }>('/api/auth/me')
      .then((u) => { setUser(u); setChecked(true) })
      .catch(() => { setUser(null); setChecked(true) })
  }, [setUser, setChecked])

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--background)]">
        <div className="space-y-3 w-64">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    )
  }

  return <Outlet />
}

/** Redirects unauthenticated users to /login. */
export function RequireAuth() {
  const { user, checked } = useAuthStore()
  const location = useLocation()

  if (!checked) return null

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}

/** Redirects already-logged-in users away from /login. */
export function RequireGuest() {
  const { user, checked } = useAuthStore()

  if (!checked) return null

  if (user) {
    return <Navigate to="/app" replace />
  }

  return <Outlet />
}
