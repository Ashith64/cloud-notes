import { useNavigate } from 'react-router-dom'
import { Settings, User, Moon, Sun, Monitor, Download, Lock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useTheme } from '@/providers/ThemeProvider'
import { useAuthStore } from '@/store/authStore'
import { cn } from '@/lib/utils'

type Theme = 'system' | 'light' | 'dark'

const THEMES: { value: Theme; label: string; icon: React.ComponentType<{ className?: string; strokeWidth?: number }> }[] = [
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
]

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { user } = useAuthStore()
  const navigate = useNavigate()

  return (
    <div className="flex flex-1 flex-col overflow-auto bg-[var(--background)]">
      <div className="max-w-2xl mx-auto w-full px-6 py-10 space-y-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent-soft)]">
            <Settings className="h-5 w-5 text-[var(--accent)]" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[var(--foreground)]">Settings</h1>
            <p className="text-sm text-[var(--muted-foreground)]">Manage your account and preferences.</p>
          </div>
        </div>

        <Separator />

        {/* Account */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Account</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--border)]">
            <div className="px-4 py-3">
              <p className="text-xs text-[var(--muted-foreground)]">Name</p>
              <p className="text-sm text-[var(--foreground)]">{user?.name}</p>
            </div>
            <div className="px-4 py-3">
              <p className="text-xs text-[var(--muted-foreground)]">Email</p>
              <p className="text-sm text-[var(--foreground)]">{user?.email}</p>
            </div>
          </div>
        </section>

        {/* Theme */}
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

        {/* Change password */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Security</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
            <div>
              <p className="text-sm text-[var(--foreground)]">Change password</p>
              <p className="text-xs text-[var(--muted-foreground)]">Update your login credentials.</p>
            </div>
            <Button variant="outline" size="sm">Change</Button>
          </div>
        </section>

        {/* Export */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Download className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Export</h2>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 flex items-center justify-between">
            <div>
              <p className="text-sm text-[var(--foreground)]">Export all notes</p>
              <p className="text-xs text-[var(--muted-foreground)]">Download a ZIP of all your notes and attachments.</p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <a href="/api/export" download>Download .zip</a>
            </Button>
          </div>
        </section>

        <div className="pt-4">
          <button onClick={() => navigate('/app')} className="text-sm text-[var(--muted-foreground)] hover:text-[var(--accent)] underline underline-offset-4 transition-colors">
            ← Back to notes
          </button>
        </div>
      </div>
    </div>
  )
}
