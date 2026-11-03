import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Outlet } from 'react-router-dom'
import {
  FileText,
  Star,
  Archive,
  Trash2,
  Plus,
  Moon,
  Sun,
  Monitor,
  Menu,
  Search,
  Settings,
  Activity,
  BookOpen,
  ChevronDown,
  Cloud,
  Hash,
  MoreHorizontal,
  Pencil,
  LogOut,
} from 'lucide-react'
import { toast } from 'sonner'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTitle, SheetDescription, SheetTrigger } from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip'
import CommandPalette from '@/components/CommandPalette'
import { useTheme } from '@/providers/ThemeProvider'
import { useAuthStore } from '@/store/authStore'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  CreateNotebookDialog,
  RenameNotebookDialog,
} from '@/components/notebooks/NotebookDialogs'
import type { Notebook, TagCount, NoteSummary, NoteDetail } from '@/types/note'

export function SidebarNav({ onClose }: { onClose?: () => void }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const currentView = searchParams.get('view') || (searchParams.get('notebook_id') || searchParams.get('tag') ? '' : 'all')
  const currentNotebookId = searchParams.get('notebook_id')
    ? Number(searchParams.get('notebook_id'))
    : null
  const currentTag = searchParams.get('tag') || null

  // Notebook dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [selectedNotebook, setSelectedNotebook] = useState<Notebook | null>(null)

  // Queries
  const { data: notebooks = [] } = useQuery<Notebook[]>({
    queryKey: ['notebooks'],
    queryFn: () => api.get<Notebook[]>('/api/notebooks'),
  })

  const { data: tags = [] } = useQuery<TagCount[]>({
    queryKey: ['tags'],
    queryFn: () => api.get<TagCount[]>('/api/tags'),
  })

  const { data: allNotes = [] } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'all', '', '', ''],
    queryFn: () => api.get<NoteSummary[]>('/api/notes?view=all&limit=200'),
  })

  const { data: favNotes = [] } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'favorites', '', '', ''],
    queryFn: () => api.get<NoteSummary[]>('/api/notes?view=favorites&limit=200'),
  })

  const { data: archiveNotes = [] } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'archive', '', '', ''],
    queryFn: () => api.get<NoteSummary[]>('/api/notes?view=archive&limit=200'),
  })

  const { data: trashNotes = [] } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'trash', '', '', ''],
    queryFn: () => api.get<NoteSummary[]>('/api/notes?view=trash&limit=200'),
  })

  // Navigation handlers
  const handleSelectView = (view: 'all' | 'favorites' | 'archive' | 'trash') => {
    const params = new URLSearchParams()
    params.set('view', view)
    const activeNote = searchParams.get('note')
    if (activeNote) params.set('note', activeNote)
    setSearchParams(params)
    onClose?.()
  }

  const handleSelectNotebook = (id: number) => {
    const params = new URLSearchParams()
    params.set('notebook_id', String(id))
    const activeNote = searchParams.get('note')
    if (activeNote) params.set('note', activeNote)
    setSearchParams(params)
    onClose?.()
  }

  const handleSelectTag = (name: string) => {
    const params = new URLSearchParams()
    params.set('tag', name)
    const activeNote = searchParams.get('note')
    if (activeNote) params.set('note', activeNote)
    setSearchParams(params)
    onClose?.()
  }

  // Notebook mutations
  const handleCreateNotebook = async (name: string) => {
    const res = await api.post<Notebook>('/api/notebooks', { name })
    queryClient.invalidateQueries({ queryKey: ['notebooks'] })
    toast.success(`Notebook "${res.name}" created`)
  }

  const handleRenameNotebook = async (id: number, newName: string) => {
    const res = await api.patch<Notebook>(`/api/notebooks/${id}`, { name: newName })
    queryClient.invalidateQueries({ queryKey: ['notebooks'] })
    toast.success(`Renamed to "${res.name}"`)
  }

  const handleDeleteNotebook = async (nb: Notebook) => {
    if (!window.confirm(`Delete notebook "${nb.name}"? Notes in it will become unfiled.`)) {
      return
    }
    try {
      await api.delete(`/api/notebooks/${nb.id}`)
      queryClient.invalidateQueries({ queryKey: ['notebooks'] })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success(`Notebook "${nb.name}" deleted`)
      if (currentNotebookId === nb.id) {
        handleSelectView('all')
      }
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete notebook')
    }
  }

  return (
    <div className="flex h-full flex-col bg-[var(--sidebar)] text-[var(--sidebar-foreground)]">
      {/* Brand Header */}
      <div className="flex items-center gap-2.5 px-4 py-3.5 border-b border-[var(--border)]">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent-soft)]">
          <Cloud className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
        </div>
        <span className="text-sm font-semibold text-[var(--foreground)] tracking-tight">
          Cloud Notes
        </span>
      </div>

      <ScrollArea className="flex-1 px-2 py-3">
        {/* Main Views Navigation */}
        <nav className="space-y-0.5">
          <button
            onClick={() => handleSelectView('all')}
            className={cn(
              'flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left',
              currentView === 'all' && !currentNotebookId && !currentTag
                ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
            )}
          >
            <div className="flex items-center gap-2.5 truncate">
              <FileText className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
              <span>All Notes</span>
            </div>
            {allNotes.length > 0 && (
              <span className="text-xs text-[var(--muted-foreground)] font-normal">
                {allNotes.length}
              </span>
            )}
          </button>

          <button
            onClick={() => handleSelectView('favorites')}
            className={cn(
              'flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left',
              currentView === 'favorites'
                ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
            )}
          >
            <div className="flex items-center gap-2.5 truncate">
              <Star className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
              <span>Favorites</span>
            </div>
            {favNotes.length > 0 && (
              <span className="text-xs text-[var(--muted-foreground)] font-normal">
                {favNotes.length}
              </span>
            )}
          </button>

          <button
            onClick={() => handleSelectView('archive')}
            className={cn(
              'flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left',
              currentView === 'archive'
                ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
            )}
          >
            <div className="flex items-center gap-2.5 truncate">
              <Archive className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
              <span>Archive</span>
            </div>
            {archiveNotes.length > 0 && (
              <span className="text-xs text-[var(--muted-foreground)] font-normal">
                {archiveNotes.length}
              </span>
            )}
          </button>

          <button
            onClick={() => handleSelectView('trash')}
            className={cn(
              'flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-sm transition-colors text-left',
              currentView === 'trash'
                ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
            )}
          >
            <div className="flex items-center gap-2.5 truncate">
              <Trash2 className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
              <span>Trash</span>
            </div>
            {trashNotes.length > 0 && (
              <span className="text-xs text-[var(--muted-foreground)] font-normal">
                {trashNotes.length}
              </span>
            )}
          </button>
        </nav>

        <Separator className="my-3" />

        {/* Notebooks Section */}
        <div className="space-y-1">
          <div className="flex items-center justify-between px-2.5 pb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
              Notebooks
            </span>
            <button
              onClick={() => setCreateDialogOpen(true)}
              aria-label="New notebook"
              className="p-1 rounded hover:bg-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          </div>

          <nav className="space-y-0.5">
            {notebooks.map((nb) => {
              const nbNoteCount = allNotes.filter((n) => n.notebook_id === nb.id).length
              const isSelected = currentNotebookId === nb.id
              return (
                <div
                  key={nb.id}
                  className={cn(
                    'group flex items-center justify-between rounded-lg px-2.5 py-1 text-sm transition-colors cursor-pointer',
                    isSelected
                      ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                      : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
                  )}
                  onClick={() => handleSelectNotebook(nb.id)}
                >
                  <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                    <BookOpen className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                    <span className="truncate">{nb.name}</span>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    {/* Note count */}
                    {nbNoteCount > 0 && (
                      <span className="text-xs text-[var(--muted-foreground)] group-hover:hidden font-normal">
                        {nbNoteCount}
                      </span>
                    )}

                    {/* Hover menu */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Options for notebook ${nb.name}`}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        >
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-36">
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedNotebook(nb)
                            setRenameDialogOpen(true)
                          }}
                        >
                          <Pencil className="mr-2 h-3.5 w-3.5" /> Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeleteNotebook(nb)
                          }}
                          className="text-[var(--destructive)] focus:text-[var(--destructive)]"
                        >
                          <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              )
            })}
          </nav>
        </div>

        <Separator className="my-3" />

        {/* Tags Section */}
        <div className="space-y-1">
          <div className="px-2.5 pb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
              Tags
            </span>
          </div>

          <nav className="space-y-0.5">
            {tags.map((tag) => {
              const isSelected = currentTag === tag.name
              return (
                <button
                  key={tag.name}
                  onClick={() => handleSelectTag(tag.name)}
                  className={cn(
                    'flex w-full items-center justify-between rounded-lg px-2.5 py-1 text-sm transition-colors text-left',
                    isSelected
                      ? 'bg-[var(--accent-soft)] text-[var(--accent)] font-semibold'
                      : 'text-[var(--sidebar-foreground)] hover:bg-[var(--border)] hover:text-[var(--foreground)]'
                  )}
                >
                  <div className="flex items-center gap-2 truncate">
                    <Hash className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
                    <span className="truncate">{tag.name}</span>
                  </div>
                  {tag.count > 0 && (
                    <span className="text-xs text-[var(--muted-foreground)] font-normal">
                      {tag.count}
                    </span>
                  )}
                </button>
              )
            })}
          </nav>
        </div>
      </ScrollArea>

      {/* Notebook Dialogs */}
      <CreateNotebookDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={handleCreateNotebook}
      />
      <RenameNotebookDialog
        notebook={selectedNotebook}
        open={renameDialogOpen}
        onOpenChange={setRenameDialogOpen}
        onRename={handleRenameNotebook}
      />
    </div>
  )
}

export default function WorkspacePage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { theme, setTheme, resolvedTheme } = useTheme()
  const { user, setUser } = useAuthStore()
  const queryClient = useQueryClient()
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
    const next: Record<string, 'light' | 'dark' | 'system'> = {
      system: 'light',
      light: 'dark',
      dark: 'system',
    }
    setTheme(next[theme])
  }

  // Create new note immediately and select it
  const handleCreateNewNote = async () => {
    try {
      const notebookIdParam = searchParams.get('notebook_id')
      const notebookId = notebookIdParam ? Number(notebookIdParam) : null
      const res = await api.post<NoteDetail>('/api/notes', {
        title: 'Untitled',
        content: '',
        notebook_id: notebookId,
      })
      queryClient.invalidateQueries({ queryKey: ['notes'] })

      const newParams = new URLSearchParams(searchParams)
      newParams.set('note', res.id)
      setSearchParams(newParams)
      toast.success('New note created')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to create note')
    }
  }

  const isMac = typeof window !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
  const modKey = isMac ? '⌘' : 'Ctrl+'
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  // Global keyboard shortcuts (Cmd+N for new note, Cmd+K for search palette, Cmd+Shift+L for theme)
  useEffect(() => {
    const handleGlobalShortcuts = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n' && !e.shiftKey) {
        e.preventDefault()
        handleCreateNewNote()
      } else if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandPaletteOpen((prev) => !prev)
      } else if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'l') {
        e.preventDefault()
        cycleTheme()
      }
    }
    window.addEventListener('keydown', handleGlobalShortcuts)
    return () => window.removeEventListener('keydown', handleGlobalShortcuts)
  }, [searchParams, cycleTheme])

  const ThemeIcon = resolvedTheme === 'dark' ? Moon : Sun
  const initials = user?.name
    ? user.name
        .split(' ')
        .map((p) => p[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?'

  return (
    <TooltipProvider delayDuration={400}>
      <div className="flex h-screen overflow-hidden bg-[var(--background)]">
        {/* Command Palette (Ctrl/Cmd+K) */}
        <CommandPalette
          open={commandPaletteOpen}
          onOpenChange={setCommandPaletteOpen}
          onSelectNote={(noteId) => {
            const params = new URLSearchParams(searchParams)
            params.set('note', noteId)
            setSearchParams(params)
          }}
          onCreateNote={handleCreateNewNote}
          onToggleTheme={cycleTheme}
          onSelectNotebook={(nbId) => {
            const params = new URLSearchParams()
            params.set('notebook_id', String(nbId))
            setSearchParams(params)
          }}
        />

        {/* Desktop Sidebar — 248px fixed width (C2), hidden below 1024px */}
        <aside className="hidden lg:flex w-[248px] flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)]">
          <SidebarNav />
        </aside>

        {/* Mobile / Tablet Drawer — shown below 1024px */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="left" className="p-0 bg-[var(--sidebar)] w-[248px]">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SheetDescription className="sr-only">Main sidebar navigation drawer</SheetDescription>
            <SidebarNav onClose={() => setDrawerOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* Main Content Area */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* Top Bar (C3.2) */}
          <header className="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4">
            {/* Hamburger Button — visible on tablet/mobile */}
            <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
                  <Menu className="h-[18px] w-[18px]" strokeWidth={1.75} />
                </Button>
              </SheetTrigger>
            </Sheet>

            {/* Top Search Button / Input (opens Command Palette per requirement 3) */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => setCommandPaletteOpen(true)}
                  className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 h-8 max-w-sm text-xs sm:text-sm text-[var(--muted-foreground)] hover:border-[var(--accent)] transition-colors text-left"
                  aria-label="Open search and command palette"
                  data-testid="search-palette-trigger"
                >
                  <Search className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" strokeWidth={1.75} />
                  <span className="flex-1 truncate">Search notes…</span>
                  <kbd className="ml-auto hidden sm:inline-flex h-5 items-center rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 font-mono text-[10px] text-[var(--muted-foreground)]">
                    {modKey}K
                  </kbd>
                </button>
              </TooltipTrigger>
              <TooltipContent>Search notes ({modKey}K)</TooltipContent>
            </Tooltip>

            {/* Right Action Icons */}
            <div className="flex items-center gap-1.5 ml-auto">
              {/* New note button */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="sm"
                    onClick={handleCreateNewNote}
                    className="gap-1.5 hidden sm:inline-flex"
                    data-testid="new-note-button"
                  >
                    <Plus className="h-4 w-4" strokeWidth={1.75} />
                    <span>New note</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>New note ({modKey}N)</TooltipContent>
              </Tooltip>

              <Button
                size="icon"
                variant="ghost"
                onClick={handleCreateNewNote}
                className="sm:hidden"
                aria-label="New note"
              >
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
                    {theme === 'system' ? (
                      <Monitor className="h-[18px] w-[18px]" strokeWidth={1.75} />
                    ) : (
                      <ThemeIcon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle theme ({modKey}⇧L)</TooltipContent>
              </Tooltip>

              {/* Avatar menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    className="flex items-center gap-1.5 rounded-lg px-1.5 py-1 hover:bg-[var(--muted)] transition-colors"
                    aria-label="User menu"
                  >
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                    </Avatar>
                    <ChevronDown
                      className="h-3 w-3 text-[var(--muted-foreground)]"
                      strokeWidth={1.75}
                    />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">
                        {user?.name}
                      </p>
                      <p className="text-xs text-[var(--muted-foreground)] truncate">
                        {user?.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate('/settings')}>
                    <Settings className="mr-2 h-4 w-4" strokeWidth={1.75} /> Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => navigate('/status')}>
                    <Activity className="mr-2 h-4 w-4" strokeWidth={1.75} /> System Status
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-[var(--destructive)]">
                    <LogOut className="mr-2 h-4 w-4" strokeWidth={1.75} /> Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>

          {/* Subroutes (WorkspaceHome / Note detail) */}
          <main className="flex flex-1 min-h-0 overflow-hidden">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
