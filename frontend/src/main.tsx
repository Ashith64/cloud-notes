import './index.css'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { ThemeProvider } from '@/providers/ThemeProvider'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AuthProvider, RequireAuth, RequireGuest } from '@/components/AuthGuard'
import NetworkBanner from '@/components/NetworkBanner'
import { queryClient } from '@/lib/queryClient'
import { useAuthStore } from '@/store/authStore'

import LoginPage from '@/pages/LoginPage'
import WorkspacePage from '@/pages/WorkspacePage'
import WorkspaceHome from '@/pages/WorkspaceHome'
import SettingsPage from '@/pages/SettingsPage'
import StatusPage from '@/pages/StatusPage'
import NotFoundPage from '@/pages/NotFoundPage'

function AuthRedirect() {
  const { user } = useAuthStore()
  return <Navigate to={user ? '/app' : '/login'} replace />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <BrowserRouter>
            <NetworkBanner />
            <Routes>
              {/* Public: status (no auth required) */}
              <Route path="/status" element={<StatusPage />} />

              {/* Auth gate: resolves /api/auth/me, shows skeleton while pending */}
              <Route element={<AuthProvider />}>
                {/* Guests only — redirect logged-in users to /app */}
                <Route element={<RequireGuest />}>
                  <Route path="/login" element={<LoginPage />} />
                </Route>

                {/* Authenticated only */}
                <Route element={<RequireAuth />}>
                  <Route path="/app" element={<WorkspacePage />}>
                    <Route index element={<WorkspaceHome />} />
                  </Route>
                  <Route path="/settings" element={<WorkspacePage />}>
                    <Route index element={<SettingsPage />} />
                  </Route>
                </Route>

                {/* Root redirect */}
                <Route path="/" element={<AuthRedirect />} />
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </BrowserRouter>

          <Toaster
            position="bottom-right"
            richColors
            closeButton
            toastOptions={{ duration: 4000 }}
          />
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
