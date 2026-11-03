import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Cloud, BookOpen, Lock, Zap, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/store/authStore'
import { queryClient } from '@/lib/queryClient'

type Mode = 'login' | 'register'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setUser } = useAuthStore()

  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(
    searchParams.get('expired') === '1'
      ? 'Your session has expired. Please log in again.'
      : null
  )

  useEffect(() => {
    document.title = mode === 'login' ? 'Sign In - Cloud Notes' : 'Create Account - Cloud Notes'
  }, [mode])

  useEffect(() => {
    if (searchParams.get('expired') === '1') {
      toast.error('Your session has expired. Please log in again.')
    }
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = mode === 'login' ? { email, password } : { name, email, password }
      const user = await api.post<{ id: number; email: string; name: string }>(endpoint, body)
      setUser(user)
      queryClient.clear()
      navigate('/app', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401 || err.status === 400) {
          setError("That email or password doesn't look right.")
        } else if (err.status === 409) {
          setError('An account with that email already exists.')
        } else if (err.status === 429) {
          setError('Too many attempts. Please wait a few minutes.')
        } else {
          setError(err.message)
        }
      } else {
        setError("Can't reach the server. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDemo = async () => {
    setError(null)
    setLoading(true)
    try {
      const user = await api.post<{ id: number; email: string; name: string }>('/api/auth/demo')
      setUser(user)
      queryClient.clear()
      toast.success('Welcome! Your demo workspace is ready.')
      navigate('/app', { replace: true })
    } catch {
      setError("Can't reach the server. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Brand panel — hidden on mobile */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[560px] flex-col justify-between p-12 bg-gradient-to-br from-indigo-600 via-indigo-500 to-violet-600 text-white flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20">
            <Cloud className="h-5 w-5 text-white" strokeWidth={1.75} />
          </div>
          <span className="text-lg font-semibold tracking-tight">Cloud Notes</span>
        </div>

        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-bold leading-tight tracking-tight">
              Your notes,<br />anywhere.
            </h1>
            <p className="mt-4 text-indigo-200 text-lg">
              A calm, focused workspace for students.
            </p>
          </div>
          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15">
                <BookOpen className="h-4 w-4" strokeWidth={1.75} />
              </div>
              <div>
                <p className="font-medium">Rich Markdown editor</p>
                <p className="text-sm text-indigo-200">Headings, code blocks, tables, checklists — everything you need.</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15">
                <Lock className="h-4 w-4" strokeWidth={1.75} />
              </div>
              <div>
                <p className="font-medium">Private and secure</p>
                <p className="text-sm text-indigo-200">Your notes are stored privately on AWS S3 — only you can access them.</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/15">
                <Zap className="h-4 w-4" strokeWidth={1.75} />
              </div>
              <div>
                <p className="font-medium">Autosave, always</p>
                <p className="text-sm text-indigo-200">Never lose a thought — notes save automatically as you type.</p>
              </div>
            </li>
          </ul>
        </div>

        <p className="text-sm text-indigo-300">
          Built on AWS · React + Flask · Tailwind CSS
        </p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center p-6 sm:p-12 bg-[var(--background)]">
        <div className="w-full max-w-md space-y-8">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--accent-soft)]">
              <Cloud className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
            </div>
            <span className="text-base font-semibold text-[var(--foreground)]">Cloud Notes</span>
          </div>

          <div>
            <h2 className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {mode === 'login'
                ? 'Sign in to continue to your workspace.'
                : 'Get started with a free account.'}
            </p>
          </div>

          {/* Demo button */}
          <Button
            type="button"
            variant="outline"
            className="w-full gap-2"
            onClick={handleDemo}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
            )}
            Try demo account
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--border)]" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[var(--background)] px-3 text-[var(--muted-foreground)] tracking-widest">
                or continue with email
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div className="space-y-1.5">
                <Label htmlFor="name">Full name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="Alex Johnson"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoComplete="name"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete={mode === 'login' ? 'username' : 'email'}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={mode === 'register' ? 'At least 8 characters' : '••••••••'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" strokeWidth={1.75} /> : <Eye className="h-4 w-4" strokeWidth={1.75} />}
                </button>
              </div>
            </div>

            {error && (
              <p role="alert" className="text-sm text-[var(--destructive)] bg-[var(--destructive)]/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> {mode === 'login' ? 'Signing in…' : 'Creating account…'}</>
              ) : (
                mode === 'login' ? 'Sign in' : 'Create account'
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-[var(--muted-foreground)]">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              type="button"
              className="font-medium text-[var(--accent)] hover:underline"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
