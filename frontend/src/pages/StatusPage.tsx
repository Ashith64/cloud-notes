import { useEffect, useState } from 'react'
import { Server, Database, HardDrive, Cpu, Clock, RefreshCw, CheckCircle2, AlertCircle, XCircle, Cloud } from 'lucide-react'
import { api, ApiError } from '@/lib/api'

interface StatusData {
  instance_id: string
  availability_zone: string
  running_servers: number | null
  average_cpu: number | null
  db_ok: boolean
  storage_ok: boolean
  last_backup: string | null
  version: string
  uptime_seconds: number
}

function StatusDot({ ok, loading }: { ok: boolean | null; loading?: boolean }) {
  if (loading) return <div className="h-2.5 w-2.5 rounded-full bg-[var(--muted-foreground)] animate-pulse" />
  if (ok === null) return <div className="h-2.5 w-2.5 rounded-full bg-amber-400" />
  return ok
    ? <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
    : <div className="h-2.5 w-2.5 rounded-full bg-red-500 animate-pulse" />
}

function StatusBadge({ ok }: { ok: boolean | null }) {
  if (ok === null) return <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-300"><AlertCircle className="h-3 w-3" /> Unknown</span>
  return ok
    ? <span className="inline-flex items-center gap-1 rounded-full bg-green-50 dark:bg-green-950 px-2.5 py-1 text-xs font-medium text-green-700 dark:text-green-300"><CheckCircle2 className="h-3 w-3" /> Healthy</span>
    : <span className="inline-flex items-center gap-1 rounded-full bg-red-50 dark:bg-red-950 px-2.5 py-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle className="h-3 w-3" /> Error</span>
}

function formatUptime(s: number): string {
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${s % 60}s`
}

function formatDate(iso: string | null): string {
  if (!iso) return 'N/A'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function StatusPage() {
  const [status, setStatus] = useState<StatusData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchStatus = async () => {
    try {
      const data = await api.get<StatusData>('/api/status')
      setStatus(data)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to fetch status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--accent-soft)]">
              <Cloud className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
            </div>
            <div>
              <h1 className="text-base font-semibold text-[var(--foreground)]">System Status</h1>
              <p className="text-xs text-[var(--muted-foreground)]">Cloud Notes · Auto-refreshes every 5 seconds</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Loading…'}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {error && (
          <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/50 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Overall status banner */}
        {status && (
          <div className={`rounded-xl border px-5 py-4 flex items-center gap-3 ${
            status.db_ok && status.storage_ok
              ? 'border-green-200 dark:border-green-900 bg-green-50 dark:bg-green-950/50'
              : 'border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/50'
          }`}>
            <StatusDot ok={status.db_ok && status.storage_ok} />
            <div>
              <p className={`text-sm font-semibold ${status.db_ok && status.storage_ok ? 'text-green-800 dark:text-green-200' : 'text-red-800 dark:text-red-200'}`}>
                {status.db_ok && status.storage_ok ? 'All systems operational' : 'Some systems are degraded'}
              </p>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                v{status.version} · Uptime {formatUptime(status.uptime_seconds)}
              </p>
            </div>
          </div>
        )}

        {/* Card grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Instance card */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                <span className="text-sm font-medium text-[var(--foreground)]">Instance</span>
              </div>
              <StatusDot ok={!!status?.instance_id} loading={loading} />
            </div>
            <div className="space-y-2">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Instance ID</p>
                <p className="text-sm font-mono text-[var(--foreground)] truncate">{status?.instance_id ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Availability Zone</p>
                <p className="text-sm text-[var(--foreground)]">{status?.availability_zone ?? '—'}</p>
              </div>
            </div>
          </div>

          {/* Running servers */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                <span className="text-sm font-medium text-[var(--foreground)]">Compute</span>
              </div>
              <StatusDot ok={true} loading={loading} />
            </div>
            <div className="space-y-2">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Running servers</p>
                <p className="text-2xl font-bold text-[var(--foreground)]">
                  {status?.running_servers ?? <span className="text-base text-[var(--muted-foreground)]">N/A</span>}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Average CPU</p>
                <p className="text-sm text-[var(--foreground)]">
                  {status?.average_cpu != null ? `${status.average_cpu.toFixed(1)}%` : 'N/A'}
                </p>
              </div>
            </div>
          </div>

          {/* Database */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                <span className="text-sm font-medium text-[var(--foreground)]">Database</span>
              </div>
              <StatusDot ok={status?.db_ok ?? null} loading={loading} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <StatusBadge ok={status?.db_ok ?? null} />
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">MySQL · SELECT 1 health check</p>
            </div>
          </div>

          {/* Storage */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                <span className="text-sm font-medium text-[var(--foreground)]">Storage</span>
              </div>
              <StatusDot ok={status?.storage_ok ?? null} loading={loading} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <StatusBadge ok={status?.storage_ok ?? null} />
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">S3 / Local · Write &amp; read probe</p>
            </div>
          </div>

          {/* Last Backup */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                <span className="text-sm font-medium text-[var(--foreground)]">Last Backup</span>
              </div>
              <StatusDot ok={status?.last_backup != null} loading={loading} />
            </div>
            <div className="space-y-1">
              <p className="text-sm text-[var(--foreground)]">
                {status ? formatDate(status.last_backup) : '—'}
              </p>
              <p className="text-xs text-[var(--muted-foreground)]">RDS automated snapshot</p>
            </div>
          </div>

          {/* App version */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <Cloud className="h-4 w-4 text-[var(--muted-foreground)]" strokeWidth={1.75} />
              <span className="text-sm font-medium text-[var(--foreground)]">Application</span>
            </div>
            <div className="space-y-2">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Version</p>
                <p className="text-sm font-mono text-[var(--foreground)]">{status?.version ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Uptime</p>
                <p className="text-sm text-[var(--foreground)]">{status ? formatUptime(status.uptime_seconds) : '—'}</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-[var(--muted-foreground)]">
          <a href="/app" className="hover:text-[var(--accent)] underline underline-offset-4 transition-colors">← Back to app</a>
        </p>
      </main>
    </div>
  )
}
