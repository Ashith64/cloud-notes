import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  Plus,
  Sun,
  BookOpen,
  Activity,
  Settings,
} from 'lucide-react'
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from '@/components/ui/command'
import { api } from '@/lib/api'
import type { NoteSummary, Notebook } from '@/types/note'

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelectNote: (noteId: string) => void
  onCreateNote: () => void
  onToggleTheme: () => void
  onSelectNotebook: (notebookId: number) => void
}

function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query.trim() || !text) return <>{text}</>
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, i) =>
        regex.test(part) ? (
          <span
            key={i}
            className="rounded bg-[var(--accent-soft)] px-0.5 font-bold text-[var(--accent)]"
          >
            {part}
          </span>
        ) : (
          part
        )
      )}
    </>
  )
}

export default function CommandPalette({
  open,
  onOpenChange,
  onSelectNote,
  onCreateNote,
  onToggleTheme,
  onSelectNotebook,
}: CommandPaletteProps) {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // 200 ms debounce per requirement 3
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
    }, 200)
    return () => clearTimeout(timer)
  }, [search])

  // Clear query on close
  useEffect(() => {
    if (!open) {
      setSearch('')
      setDebouncedSearch('')
    }
  }, [open])

  // Query matching notes when debounced search is not empty
  const { data: searchResults = [], isLoading: isSearching } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'search-palette', debouncedSearch],
    queryFn: () => api.get<NoteSummary[]>(`/api/notes?q=${encodeURIComponent(debouncedSearch)}`),
    enabled: open && debouncedSearch.trim().length > 0,
  })

  // Query recent notes when search is empty
  const { data: recentNotes = [] } = useQuery<NoteSummary[]>({
    queryKey: ['notes', 'recent-palette'],
    queryFn: () => api.get<NoteSummary[]>('/api/notes?sort=updated&limit=5'),
    enabled: open && debouncedSearch.trim().length === 0,
  })

  // Query notebooks list for "Go to notebook" actions
  const { data: notebooks = [] } = useQuery<Notebook[]>({
    queryKey: ['notebooks'],
    queryFn: () => api.get<Notebook[]>('/api/notebooks'),
    enabled: open,
  })

  const isMac = typeof window !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
  const modKey = isMac ? '⌘' : 'Ctrl+'

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="Type a command or search notes…"
        value={search}
        onValueChange={setSearch}
      />
      <CommandList>
        <CommandEmpty>
          {isSearching
            ? 'Searching…'
            : debouncedSearch
            ? `No notes found matching "${debouncedSearch}".`
            : 'No results.'}
        </CommandEmpty>

        {/* Live Search Results with Match Highlighting */}
        {debouncedSearch.trim().length > 0 && searchResults.length > 0 && (
          <CommandGroup heading="Matching Notes">
            {searchResults.map((note) => (
              <CommandItem
                key={note.id}
                value={`${note.title} ${note.snippet || ''} note-${note.id}`}
                onSelect={() => {
                  onSelectNote(note.id)
                  onOpenChange(false)
                }}
                className="flex items-start gap-2.5 py-2.5 cursor-pointer"
              >
                <FileText className="h-4 w-4 text-[var(--accent)] shrink-0 mt-0.5" />
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-sm font-medium text-[var(--foreground)] truncate">
                    <HighlightText text={note.title || 'Untitled'} query={debouncedSearch} />
                  </span>
                  {note.snippet && (
                    <span className="text-xs text-[var(--muted-foreground)] line-clamp-1 mt-0.5">
                      <HighlightText text={note.snippet} query={debouncedSearch} />
                    </span>
                  )}
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {/* When empty: Recent notes + Actions list */}
        {debouncedSearch.trim().length === 0 && (
          <>
            {recentNotes.length > 0 && (
              <CommandGroup heading="Recent Notes">
                {recentNotes.map((note) => (
                  <CommandItem
                    key={note.id}
                    value={`${note.title} recent-${note.id}`}
                    onSelect={() => {
                      onSelectNote(note.id)
                      onOpenChange(false)
                    }}
                    className="flex items-center gap-2.5 py-2 cursor-pointer"
                  >
                    <FileText className="h-4 w-4 text-[var(--muted-foreground)] shrink-0" />
                    <span className="text-sm font-medium text-[var(--foreground)] truncate flex-1">
                      {note.title || 'Untitled'}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            <CommandGroup heading="Actions">
              {/* New note */}
              <CommandItem
                value="new note create"
                onSelect={() => {
                  onOpenChange(false)
                  onCreateNote()
                }}
                className="flex items-center justify-between py-2 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Plus className="h-4 w-4 text-[var(--accent)]" />
                  <span>New note</span>
                </div>
                <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted-foreground)]">
                  {modKey}N
                </kbd>
              </CommandItem>

              {/* Toggle theme */}
              <CommandItem
                value="toggle theme switch light dark"
                onSelect={() => {
                  onOpenChange(false)
                  onToggleTheme()
                }}
                className="flex items-center justify-between py-2 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Sun className="h-4 w-4 text-[var(--accent)]" />
                  <span>Toggle theme</span>
                </div>
                <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted-foreground)]">
                  {modKey}⇧L
                </kbd>
              </CommandItem>

              {/* Go to notebook */}
              {notebooks.map((nb) => (
                <CommandItem
                  key={nb.id}
                  value={`go to notebook ${nb.name}`}
                  onSelect={() => {
                    onOpenChange(false)
                    onSelectNotebook(nb.id)
                  }}
                  className="flex items-center gap-2 py-2 cursor-pointer"
                >
                  <BookOpen className="h-4 w-4 text-[var(--muted-foreground)]" />
                  <span>Go to notebook: <strong>{nb.name}</strong></span>
                </CommandItem>
              ))}

              {/* Open System Status */}
              <CommandItem
                value="system status servers cpu health"
                onSelect={() => {
                  onOpenChange(false)
                  navigate('/status')
                }}
                className="flex items-center gap-2 py-2 cursor-pointer"
              >
                <Activity className="h-4 w-4 text-[var(--muted-foreground)]" />
                <span>Open System Status</span>
              </CommandItem>

              {/* Open Settings */}
              <CommandItem
                value="settings account storage password"
                onSelect={() => {
                  onOpenChange(false)
                  navigate('/settings')
                }}
                className="flex items-center gap-2 py-2 cursor-pointer"
              >
                <Settings className="h-4 w-4 text-[var(--muted-foreground)]" />
                <span>Open Settings</span>
              </CommandItem>
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  )
}
