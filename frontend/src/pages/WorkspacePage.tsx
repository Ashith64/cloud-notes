import { useState } from 'react'
import { useNavigate, Outlet } from 'react-router-dom'
import {
  FileText, Star, Archive, Trash2, Plus, Moon, Sun, Monitor,
  Menu, Search, LogOut, Settings, Activity, BookOpen, ChevronDown,
  Cloud, Hash,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip'
import { useTheme } from '@/providers/ThemeProvider'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/lib/api'
import { queryClient } from '@/lib/queryClient'

function SidebarContent({ onClose }: { onClose?: () => void }) {
  const navigate = useNavigate()
  const handleLink = (path: string) => { navigate(path); onClose?.() }
  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent-soft)]">
          <Cloud className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
        </div>
        <span className="text-sm font-semibold text-[var(--foreground)]">Cloud Notes</span>
      </div>
      <Separator />
      <ScrollArea className="flex-1 py-3 px-2">
        <nav className="space-y-0.5">
          <button onClick={() => handleLink('/app')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
            <FileText className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />All Notes
          </button>
          <button onClick={() => handleLink('/app')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
            <Star className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />Favorites
          </button>
          <button onClick={() => handleLink('/app')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
            <Archive className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />Archive
          </button>
          <button onClick={() => handleLink('/app')} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
            <Trash2 className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />Trash
          </button>
        </nav>

        <Separator className="my-3" />

        {/* Notebooks */}
        <div className="px-3 pb-1 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-[var(--muted-foreground)]">Notebooks</span>
          <button aria-label="New notebook" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors">
            <Plus className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </div>
        <nav className="space-y-0.5">
          {['College', 'Projects', 'Personal'].map((nb) => (
            <button key={nb} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
              <BookOpen className="h-[16px] w-[16px] shrink-0" strokeWidth={1.75} />
              {nb}
            </button>
          ))}
        </nav>

        <Separator className="my-3" />

        {/* Tags placeholder */}
        <div className="px-3 pb-1">
          <span className="text-xs font-semibold uppercase tracking-widest text-[var(--muted-foreground)]">Tags</span>
        </div>
        <nav className="space-y-0.5">
          {['aws', 'docker', 'networking'].map((tag) => (
            <button key={tag} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)] transition-colors">
              <Hash className="h-[14px] w-[14px] shrink-0" strokeWidth={1.75} />
              {tag}
            </button>
          ))}
        </nav>
      </ScrollArea>
    </div>
  )
}

export default function WorkspacePage() {
  const navigate = useNavigate()
  const { theme, setTheme, resolvedTheme } = useTheme()
  const { user, setUser } = useAuthStore()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const handleLogout = async () => {
    try {
      await api.post('/api/auth/logout')
    } catch {}
    setUser(null)
    queryClient.clear()
    navigate('/login', { replace: true })
    toast.success('You have been signed out.')
  }

  const cycleTheme = () => {
    const next: Record<string, 'light' | 'dark' | 'system'> = { system: 'light', light: 'dark', dark: 'system' }
    setTheme(next[theme])
  }

  const ThemeIcon = resolvedTheme === 'dark' ? Moon : Sun
  const initials = user?.name
    ? user.name.split(' ').map((p) => p[0]).join('').toUpperCase().slice(0, 2)
    : '?'

  return (
    <TooltipProvider delayDuration={400}>
      <div className="flex h-screen overflow-hidden bg-[var(--background)]">
        {/* Desktop Sidebar — hidden below 1024px */}
        <aside className="hidden lg:flex w-[248px] flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)]">
          <SidebarContent />
        </aside>

        {/* Mobile drawer — shown below 1024px */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="left" className="p-0 bg-[var(--sidebar)] w-[248px]">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SidebarContent onClose={() => setDrawerOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* Main area */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* Top bar */}
          <header className="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4">
            {/* Hamburger — only on tablet/phone */}
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
                  <Menu className="h-[18px] w-[18px]" strokeWidth={1.75} />
                </Button>
              </SheetTrigger>
            </Sheet>

            {/* Search */}
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 h-8 max-w-sm text-sm text-[var(--muted-foreground)] cursor-text">
              <Search className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
              <span>Search notes…</span>
              <kbd className="ml-auto hidden sm:inline-flex h-5 items-center rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 font-mono text-[10px] text-[var(--muted-foreground)]">⌘K</kbd>
            </div>

            <div className="flex items-center gap-1.5 ml-auto">
              {/* New note */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="sm" className="gap-1.5 hidden sm:inline-flex">
                    <Plus className="h-4 w-4" strokeWidth={1.75} />
                    <span>New note</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>New note (⌘N)</TooltipContent>
              </Tooltip>
              <Button size="icon" variant="ghost" className="sm:hidden" aria-label="New note">
                <Plus className="h-4 w-4" strokeWidth={1.75} />
              </Button>

              {/* Theme toggle */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={cycleTheme}
                    aria-label={`Switch theme (current: ${theme})`}
                  >
                    {theme === 'system'
                      ? <Monitor className="h-[18px] w-[18px]" strokeWidth={1.75} />
                      : <ThemeIcon className="h-[18px] w-[18px]" strokeWidth={1.75} />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Theme: {theme}</TooltipContent>
              </Tooltip>

              {/* Avatar menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 hover:bg-[var(--muted)] transition-colors" aria-label="User menu">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                    </Avatar>
                    <ChevronDown className="h-3 w-3 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium text-[var(--foreground)]">{user?.name}</p>
                      <p className="text-xs text-[var(--muted-foreground)] truncate">{user?.email}</p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/settings')}>
                    <Settings className="h-4 w-4" strokeWidth={1.75} /> Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/status')}>
                    <Activity className="h-4 w-4" strokeWidth={1.75} /> System Status
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-[var(--destructive)] focus:text-[var(--destructive)]">
                    <LogOut className="h-4 w-4" strokeWidth={1.75} /> Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>

          {/* Content */}
          <div className="flex flex-1 min-h-0">
            <Outlet />
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}
