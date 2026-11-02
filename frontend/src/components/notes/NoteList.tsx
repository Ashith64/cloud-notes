import React, { useEffect, useRef } from 'react'
import { FileText, Search, Trash2, Plus } from 'lucide-react'
import NoteCard from './NoteCard'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import type { NoteSummary, Notebook, ViewFilter } from '@/types/note'

interface NoteListProps {
  notes: NoteSummary[]
  isLoading: boolean
  selectedNoteId: string | null
  currentView: ViewFilter
  notebookId: number | null
  tagFilter: string | null
  searchQuery: string
  notebooks: Notebook[]
  hasMore?: boolean
  onLoadMore?: () => void
  onSelectNote: (id: string) => void
  onTogglePin: (id: string, e: React.MouseEvent) => void
  onToggleFavorite: (id: string, isFav: boolean) => void
  onToggleArchive: (id: string, isArchived: boolean) => void
  onDeleteNote: (id: string, e?: React.MouseEvent) => void
  onRestoreNote: (id: string) => void
  onPermanentDeleteNote: (id: string) => void
  onMoveNotebook: (id: string, notebookId: number | null) => void
  onEmptyTrash: () => void
  onCreateNote: () => void
}

export default function NoteList({
  notes,
  isLoading,
  selectedNoteId,
  currentView,
  notebookId,
  tagFilter,
  searchQuery,
  notebooks,
  hasMore = false,
  onLoadMore,
  onSelectNote,
  onTogglePin,
  onToggleFavorite,
  onToggleArchive,
  onDeleteNote,
  onRestoreNote,
  onPermanentDeleteNote,
  onMoveNotebook,
  onEmptyTrash,
  onCreateNote,
}: NoteListProps) {
  const [emptyTrashDialogOpen, setEmptyTrashDialogOpen] = React.useState(false)
  const listContainerRef = useRef<HTMLDivElement>(null)

  // Separate pinned and recent notes if in 'all' view without search
  const isAllView = currentView === 'all' && !notebookId && !tagFilter && !searchQuery
  const pinnedNotes = isAllView ? notes.filter((n) => n.is_pinned) : []
  const recentNotes = isAllView ? notes.filter((n) => !n.is_pinned) : notes

  // Flat list of all currently displayed notes for keyboard navigation
  const visibleNotes = isAllView ? [...pinnedNotes, ...recentNotes] : notes

  // Keyboard Up and Down navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input, textarea or contentEditable
      const target = e.target as HTMLElement | null
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable ||
          target.closest('.milkdown'))
      ) {
        return
      }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (visibleNotes.length === 0) return
        e.preventDefault()

        const currentIndex = visibleNotes.findIndex((n) => n.id === selectedNoteId)
        let nextIndex = currentIndex

        if (e.key === 'ArrowDown') {
          nextIndex = currentIndex < visibleNotes.length - 1 ? currentIndex + 1 : 0
        } else if (e.key === 'ArrowUp') {
          nextIndex = currentIndex > 0 ? currentIndex - 1 : visibleNotes.length - 1
        }

        const nextNote = visibleNotes[nextIndex]
        if (nextNote) {
          onSelectNote(nextNote.id)
          // Scroll item into view
          const el = listContainerRef.current?.querySelector(`[data-note-id="${nextNote.id}"]`)
          el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [visibleNotes, selectedNoteId, onSelectNote])

  // Get active view/filter heading title
  let sectionTitle = 'All Notes'
  if (currentView === 'favorites') sectionTitle = 'Favorites'
  else if (currentView === 'archive') sectionTitle = 'Archive'
  else if (currentView === 'trash') sectionTitle = 'Trash'
  else if (notebookId) {
    const nb = notebooks.find((n) => n.id === notebookId)
    sectionTitle = nb ? nb.name : 'Notebook'
  } else if (tagFilter) {
    sectionTitle = `#${tagFilter}`
  } else if (searchQuery) {
    sectionTitle = `Search: "${searchQuery}"`
  }

  return (
    <div
      ref={listContainerRef}
      className="flex flex-col h-full overflow-hidden bg-[var(--surface)] border-r border-[var(--border)]"
      data-testid="note-list-pane"
    >
      {/* Header bar */}
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--border)] px-4">
        <h2 className="text-sm font-semibold text-[var(--foreground)] truncate">
          {sectionTitle}
        </h2>

        {/* If in Trash view, offer Empty Trash button */}
        {currentView === 'trash' && notes.length > 0 && (
          <Dialog open={emptyTrashDialogOpen} onOpenChange={setEmptyTrashDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" size="sm" className="h-7 text-xs text-[var(--destructive)] hover:bg-[var(--destructive)]/10">
                <Trash2 className="h-3.5 w-3.5 mr-1" /> Empty
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Empty Trash?</DialogTitle>
                <DialogDescription>
                  All notes currently in the Trash will be permanently deleted. This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setEmptyTrashDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setEmptyTrashDialogOpen(false)
                    onEmptyTrash()
                  }}
                >
                  Empty Trash
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Trash notice per requirement 2 */}
      {currentView === 'trash' && (
        <div className="bg-[var(--muted)]/50 border-b border-[var(--border)] px-4 py-2 text-[11px] text-[var(--muted-foreground)]">
          <span>Items in Trash are permanently removed after 30 days.</span>
        </div>
      )}

      {/* Note cards scroll area */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {/* Skeleton loaders */}
        {isLoading && (
          <div className="space-y-2 p-1" data-testid="note-list-skeletons">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="rounded-xl border border-[var(--border)] p-3 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
                <div className="flex items-center justify-between pt-1">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-3 w-12" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty States */}
        {!isLoading && notes.length === 0 && (
          <div className="flex flex-col items-center justify-center p-8 text-center my-auto min-h-[300px] space-y-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-soft)]">
              {currentView === 'trash' ? (
                <Trash2 className="h-5 w-5 text-[var(--accent)]" />
              ) : searchQuery ? (
                <Search className="h-5 w-5 text-[var(--accent)]" />
              ) : (
                <FileText className="h-5 w-5 text-[var(--accent)]" />
              )}
            </div>

            <div>
              <p className="text-sm font-medium text-[var(--foreground)]">
                {currentView === 'trash'
                  ? 'Trash is empty'
                  : searchQuery
                  ? `No results for "${searchQuery}"`
                  : 'No notes yet'}
              </p>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                {currentView === 'trash'
                  ? 'Notes you delete will show up here for 30 days.'
                  : searchQuery
                  ? 'Try searching with different keywords.'
                  : 'Create your first note to get started.'}
              </p>
            </div>

            {currentView !== 'trash' && !searchQuery && (
              <Button size="sm" onClick={onCreateNote} className="gap-1.5 mt-2">
                <Plus className="h-3.5 w-3.5" />
                <span>Create note</span>
              </Button>
            )}
          </div>
        )}

        {/* Pinned section */}
        {!isLoading && pinnedNotes.length > 0 && (
          <div className="space-y-1">
            <div className="px-2 py-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                Pinned
              </span>
            </div>
            <div className="space-y-1.5">
              {pinnedNotes.map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  isSelected={note.id === selectedNoteId}
                  isTrashView={currentView === 'trash'}
                  notebooks={notebooks}
                  onSelect={onSelectNote}
                  onTogglePin={onTogglePin}
                  onToggleFavorite={onToggleFavorite}
                  onToggleArchive={onToggleArchive}
                  onDelete={onDeleteNote}
                  onRestore={onRestoreNote}
                  onPermanentDelete={onPermanentDeleteNote}
                  onMoveNotebook={onMoveNotebook}
                />
              ))}
            </div>
          </div>
        )}

        {/* Recent section */}
        {!isLoading && recentNotes.length > 0 && (
          <div className="space-y-1">
            {pinnedNotes.length > 0 && (
              <div className="px-2 py-1 pt-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Recent
                </span>
              </div>
            )}
            <div className="space-y-1.5">
              {recentNotes.map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  isSelected={note.id === selectedNoteId}
                  isTrashView={currentView === 'trash'}
                  notebooks={notebooks}
                  onSelect={onSelectNote}
                  onTogglePin={onTogglePin}
                  onToggleFavorite={onToggleFavorite}
                  onToggleArchive={onToggleArchive}
                  onDelete={onDeleteNote}
                  onRestore={onRestoreNote}
                  onPermanentDelete={onPermanentDeleteNote}
                  onMoveNotebook={onMoveNotebook}
                />
              ))}
            </div>
          </div>
        )}

        {/* Load more button */}
        {hasMore && (
          <div className="pt-2 pb-4 text-center">
            <Button
              variant="outline"
              size="sm"
              onClick={onLoadMore}
              className="w-full text-xs"
            >
              Load more
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
