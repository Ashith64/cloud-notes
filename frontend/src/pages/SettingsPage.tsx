import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Settings,
  User,
  Moon,
  Sun,
  Monitor,
  Download,
  Lock,
  HardDrive,
  Loader2,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useTheme } from '@/providers/ThemeProvider'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/lib/api'
import { cn, formatBytes } from '@/lib/utils'

type Theme = 'system' | 'light' | 'dark'

interface StorageUsage {
  notes_bytes: number
  attachments_bytes: number
  total_bytes: number
  limit_bytes: number
}

const THEMES: {
  value: Theme
  label: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
}[] = [
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
]

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { user } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Settings - Cloud Notes'
  }, [])

  // Storage usage query
  const { data: storage, isLoading: isStorageLoading } = useQuery<StorageUsage>({
    queryKey: ['user-storage'],
    queryFn: () => api.get<StorageUsage>('/api/user/storage'),
  })

  // Change password form state
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess(false)

    if (!oldPassword) {
      setPasswordError('Please enter your current password.')
      return
    }

    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.')
      return
    }

    setIsSubmittingPassword(true)
    try {
      await api.post('/api/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })
      toast.success('Password updated successfully.')
      setPasswordSuccess(true)
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => {
        setIsChangingPassword(false)
        setPasswordSuccess(false)
      }, 2000)
    } catch (err: any) {
      setPasswordError(err?.message || 'Failed to update password.')
    } finally {
      setIsSubmittingPassword(false)
    }
  }

  const limitBytes = storage?.limit_bytes || 100 * 1024 * 1024 // 100 MB limit
  const totalBytes = storage?.total_bytes || 0
  const usedPercent = Math.min(100, Math.max(totalBytes > 0 ? 1 : 0, (totalBytes / limitBytes) * 100))

  return (
    <div className="flex flex-1 flex-col overflow-auto bg-[var(--background)]">
      <div className="max-w-2xl mx-auto w-full px-6 py-10 space-y-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent-soft)]">
            <Settings className="h-5 w-5 text-[var(--accent)]" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--foreground)]">Settings</h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Manage your account and preferences.
            </p>
          </div>
        </div>

        <Separator />

        {/* Account Info */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Account</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]">
            <div className="px-4 py-3">
              <p className="text-xs text-[var(--muted-foreground)]">Name</p>
              <p className="text-sm font-medium text-[var(--foreground)]">{user?.name || 'User'}</p>
            </div>
            <div className="px-4 py-3">
              <p className="text-xs text-[var(--muted-foreground)]">Email</p>
              <p className="text-sm font-medium text-[var(--foreground)]">{user?.email}</p>
            </div>
          </div>
        </section>

        {/* Storage Used per C3.4 */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Storage</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-[var(--foreground)]">
                {isStorageLoading ? (
                  'Calculating storage…'
                ) : (
                  `${formatBytes(totalBytes)} of 100 MB used`
                )}
              </span>
              <span className="text-xs text-[var(--muted-foreground)]">
                {usedPercent.toFixed(1)}%
              </span>
            </div>

            {/* Storage Progress Bar */}
            <div className="h-2.5 w-full rounded-full bg-[var(--muted)] overflow-hidden">
              <div
                className="h-full bg-[var(--accent)] rounded-full transition-all duration-300"
                style={{ width: `${usedPercent}%` }}
                data-testid="storage-progress-bar"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)] pt-1">
              <span>Notes: {formatBytes(storage?.notes_bytes || 0)}</span>
              <span>Attachments: {formatBytes(storage?.attachments_bytes || 0)}</span>
              <span>Limit: 100 MB</span>
            </div>
          </div>
        </section>

        {/* Theme Choice */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Sun className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Theme</h2>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {THEMES.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-xl border p-4 text-sm transition-colors duration-150',
                  theme === value
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                    : 'border-[var(--border)] bg-[var(--surface)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]'
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={1.75} />
                <span className="font-medium">{label}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Change password with validation */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Security</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
            {!isChangingPassword ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--foreground)]">Change password</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Update your account password with at least 8 characters.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setIsChangingPassword(true)
                    setPasswordError('')
                    setPasswordSuccess(false)
                  }}
                  data-testid="change-password-toggle"
                >
                  Change
                </Button>
              </div>
            ) : (
              <form onSubmit={handlePasswordSubmit} className="space-y-4" data-testid="change-password-form">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--foreground)]">
                    Update your password
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Choose a strong password with at least 8 characters.
                  </p>
                </div>

                {passwordError && (
                  <div className="rounded-lg bg-[var(--destructive)]/10 border border-[var(--destructive)]/20 p-2.5 text-xs text-[var(--destructive)]">
                    {passwordError}
                  </div>
                )}

                {passwordSuccess && (
                  <div className="rounded-lg bg-[var(--success)]/10 border border-[var(--success)]/20 p-2.5 text-xs text-[var(--success)] flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span>Password updated successfully!</span>
                  </div>
                )}

                <div className="space-y-3">
                  <div className="space-y-1">
                    <Label htmlFor="old-password">Current password</Label>
                    <Input
                      id="old-password"
                      type="password"
                      value={oldPassword}
                      onChange={(e) => setOldPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="new-password">New password (min 8 chars)</Label>
                    <Input
                      id="new-password"
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      minLength={8}
                      required
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="confirm-password">Confirm new password</Label>
                    <Input
                      id="confirm-password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      minLength={8}
                      required
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isSubmittingPassword}
                    data-testid="submit-new-password"
                  >
                    {isSubmittingPassword ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                        Updating…
                      </>
                    ) : (
                      'Update password'
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={isSubmittingPassword}
                    onClick={() => {
                      setIsChangingPassword(false)
                      setPasswordError('')
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>
        </section>

        {/* Export All as ZIP */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Download className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Export</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--foreground)]">Export all notes</p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Download a ZIP containing all your markdown notes and attachments folder.
              </p>
            </div>
            <Button variant="outline" size="sm" asChild data-testid="export-zip-button">
              <a href="/api/export" download="cloudnotes-export.zip">
                <Download className="h-3.5 w-3.5 mr-1.5" /> Download .zip
              </a>
            </Button>
          </div>
        </section>

        <div className="pt-4">
          <button
            onClick={() => navigate('/app')}
            className="text-sm text-[var(--muted-foreground)] hover:text-[var(--accent)] underline underline-offset-4 transition-colors"
          >
            ← Back to notes
          </button>
        </div>
      </div>
    </div>
  )
}
