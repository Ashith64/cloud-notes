import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FileText, ArrowLeft, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import NoteList from '@/components/notes/NoteList'
import NoteEditor from '@/components/editor/NoteEditor'
import { api } from '@/lib/api'
import type { NoteSummary, NoteDetail, Notebook, ViewFilter } from '@/types/note'

export default function WorkspaceHome() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [justCreatedId, setJustCreatedId] = useState<string | null>(null)

  // Current URL state
  const currentView = (searchParams.get('view') as ViewFilter) || (searchParams.get('notebook_id') || searchParams.get('tag') ? 'all' : 'all')
  const notebookId = searchParams.get('notebook_id')
    ? Number(searchParams.get('notebook_id'))
    : null
  const tagFilter = searchParams.get('tag') || null
  const searchQuery = searchParams.get('q') || ''
  const activeNoteId = searchParams.get('note') || null

  // Notebooks query
  const { data: notebooks = [] } = useQuery<Notebook[]>({
    queryKey: ['notebooks'],
    queryFn: () => api.get<Notebook[]>('/api/notebooks'),
  })

  // Notes list query
  const notesQueryUrl = useMemo(() => {
    const params = new URLSearchParams()
    if (currentView) params.set('view', currentView)
    if (notebookId) params.set('notebook_id', String(notebookId))
    if (tagFilter) params.set('tag', tagFilter)
    if (searchQuery) params.set('q', searchQuery)
    params.set('limit', '50')
    return `/api/notes?${params.toString()}`
  }, [currentView, notebookId, tagFilter, searchQuery])

  const {
    data: notes = [],
    isLoading: isNotesLoading,
  } = useQuery<NoteSummary[]>({
    queryKey: ['notes', currentView, notebookId ?? '', tagFilter ?? '', searchQuery],
    queryFn: () => api.get<NoteSummary[]>(notesQueryUrl),
  })

  // Selected note detail query
  const {
    data: activeNote,
    isLoading: isNoteLoading,
  } = useQuery<NoteDetail>({
    queryKey: ['note', activeNoteId],
    queryFn: () => api.get<NoteDetail>(`/api/notes/${activeNoteId}`),
    enabled: !!activeNoteId,
  })

  // Select note
  const handleSelectNote = (id: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('note', id)
    setSearchParams(params)
    setJustCreatedId(null)
  }

  // Back button for mobile view
  const handleBackToList = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('note')
    setSearchParams(params)
    setJustCreatedId(null)
  }

  // Create note
  const handleCreateNote = async () => {
    try {
      const res = await api.post<NoteDetail>('/api/notes', {
        title: 'Untitled',
        content: '',
        notebook_id: notebookId,
      })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      queryClient.setQueryData(['note', res.id], res)

      setJustCreatedId(res.id)
      const params = new URLSearchParams(searchParams)
      params.set('note', res.id)
      setSearchParams(params)
      toast.success('New note created')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to create note')
    }
  }

  // Pin toggle
  const handleTogglePin = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const target = notes.find((n) => n.id === id)
    if (!target) return
    const nextPinned = !target.is_pinned

    // Optimistic update
    queryClient.setQueriesData<NoteSummary[]>({ queryKey: ['notes'] }, (old) => {
      if (!old) return old
      return old.map((n) => (n.id === id ? { ...n, is_pinned: nextPinned } : n))
    })

    try {
      await api.patch(`/api/notes/${id}`, { is_pinned: nextPinned })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success(nextPinned ? 'Note pinned' : 'Note unpinned')
    } catch (err: any) {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.error(err?.message || 'Failed to update pin')
    }
  }

  // Favorite toggle
  const handleToggleFavorite = async (id: string, isFav: boolean) => {
    try {
      await api.patch(`/api/notes/${id}`, { is_favorite: isFav })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success(isFav ? 'Added to favorites' : 'Removed from favorites')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to update favorite')
    }
  }

  // Archive toggle
  const handleToggleArchive = async (id: string, isArchived: boolean) => {
    try {
      await api.patch(`/api/notes/${id}`, { is_archived: isArchived })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success(isArchived ? 'Note archived' : 'Note unarchived')
      if (activeNoteId === id) {
        // Deselect or keep
      }
    } catch (err: any) {
      toast.error(err?.message || 'Failed to archive note')
    }
  }

  // Delete note (move to trash with 6s Undo toast)
  const handleDeleteNote = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      await api.delete(`/api/notes/${id}`)
      queryClient.invalidateQueries({ queryKey: ['notes'] })

      // Clear selection if this note was selected
      if (activeNoteId === id) {
        const remaining = notes.filter((n) => n.id !== id)
        const params = new URLSearchParams(searchParams)
        if (remaining.length > 0) {
          params.set('note', remaining[0].id)
        } else {
          params.delete('note')
        }
        setSearchParams(params)
      }

      toast('Moved to Trash', {
        duration: 6000,
        action: {
          label: 'Undo',
          onClick: async () => {
            try {
              await api.post(`/api/notes/${id}/restore`)
              queryClient.invalidateQueries({ queryKey: ['notes'] })
              handleSelectNote(id)
              toast.success('Note restored')
            } catch {
              toast.error('Failed to restore note')
            }
          },
        },
      })
    } catch (err: any) {
      toast.error(err?.message || 'Failed to move note to trash')
    }
  }

  // Restore note
  const handleRestoreNote = async (id: string) => {
    try {
      await api.post(`/api/notes/${id}/restore`)
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      toast.success('Note restored')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to restore note')
    }
  }

  // Permanent delete
  const handlePermanentDeleteNote = async (id: string) => {
    if (!window.confirm('Permanently delete this note? This action cannot be undone.')) {
      return
    }
    try {
      await api.delete(`/api/notes/${id}/permanent`)
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      if (activeNoteId === id) {
        handleBackToList()
      }
      toast.success('Note permanently deleted')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to permanently delete note')
    }
  }

  // Empty trash
  const handleEmptyTrash = async () => {
    try {
      await api.post('/api/trash/empty')
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      handleBackToList()
      toast.success('Trash emptied')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to empty trash')
    }
  }

  // Move notebook
  const handleMoveNotebook = async (id: string, newNotebookId: number | null) => {
    try {
      await api.patch(`/api/notes/${id}`, { notebook_id: newNotebookId })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      queryClient.invalidateQueries({ queryKey: ['note', id] })
      toast.success('Note moved')
    } catch (err: any) {
      toast.error(err?.message || 'Failed to move note')
    }
  }

  return (
    <div className="flex flex-1 h-full min-w-0 overflow-hidden">
      {/* Note list pane — 340px fixed width (C2), hidden on phone when note is active */}
      <div
        className={`w-full sm:w-[340px] flex-shrink-0 h-full ${
          activeNoteId ? 'hidden sm:flex flex-col' : 'flex flex-col'
        }`}
      >
        <NoteList
          notes={notes}
          isLoading={isNotesLoading}
          selectedNoteId={activeNoteId}
          currentView={currentView}
          notebookId={notebookId}
          tagFilter={tagFilter}
          searchQuery={searchQuery}
          notebooks={notebooks}
          onSelectNote={handleSelectNote}
          onTogglePin={handleTogglePin}
          onToggleFavorite={handleToggleFavorite}
          onToggleArchive={handleToggleArchive}
          onDeleteNote={handleDeleteNote}
          onRestoreNote={handleRestoreNote}
          onPermanentDeleteNote={handlePermanentDeleteNote}
          onMoveNotebook={handleMoveNotebook}
          onEmptyTrash={handleEmptyTrash}
          onCreateNote={handleCreateNote}
        />

        {/* Floating + button on phone when viewing list per requirement 6 */}
        {!activeNoteId && (
          <button
            type="button"
            onClick={handleCreateNote}
            className="sm:hidden fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-xl bg-[var(--accent)] text-white hover:bg-[var(--accent)]/90 flex items-center justify-center z-20 transition-transform active:scale-95"
            aria-label="Create note"
            data-testid="mobile-floating-plus"
          >
            <Plus className="h-6 w-6" strokeWidth={2} />
          </button>
        )}
      </div>

      {/* Note Editor pane — takes remaining space, hidden on mobile when no note selected */}
      <div
        className={`flex-1 flex flex-col h-full min-w-0 bg-[var(--surface)] ${
          !activeNoteId ? 'hidden sm:flex' : 'flex'
        }`}
      >
        {/* Mobile back button header (< 640px) */}
        {activeNoteId && (
          <div className="sm:hidden flex items-center gap-2 border-b border-[var(--border)] px-4 py-2 bg-[var(--surface)]">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleBackToList}
              className="gap-1 text-xs text-[var(--muted-foreground)] -ml-2"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Notes</span>
            </Button>
          </div>
        )}

        {/* Editor or loading/empty state */}
        {activeNoteId ? (
          isNoteLoading && !activeNote ? (
            <div className="flex-1 p-8 max-w-[720px] mx-auto w-full space-y-6">
              <Skeleton className="h-10 w-3/4" />
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-5 w-16" />
              </div>
              <Skeleton className="h-64 w-full" />
            </div>
          ) : activeNote ? (
            <NoteEditor
              key={activeNote.id}
              note={activeNote}
              autoFocusTitle={justCreatedId === activeNote.id}
              onNoteUpdated={(updated) => {
                queryClient.setQueryData(['note', updated.id], updated)
                queryClient.invalidateQueries({ queryKey: ['notes'] })
              }}
              onDeleteNote={handleDeleteNote}
              onRestoreNote={handleRestoreNote}
              onPermanentDeleteNote={handlePermanentDeleteNote}
              onToggleArchive={handleToggleArchive}
              onMoveNotebook={handleMoveNotebook}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center p-8 text-center text-sm text-[var(--muted-foreground)]">
              Note could not be found.
            </div>
          )
        ) : (
          /* Empty state: No note selected */
          <div className="flex-1 flex items-center justify-center p-8 bg-[var(--background)]">
            <div className="text-center p-8 space-y-3 max-w-sm">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--muted)]">
                <FileText className="h-6 w-6 text-[var(--muted-foreground)]" strokeWidth={1.75} />
              </div>
              <p className="text-sm font-medium text-[var(--foreground)]">
                Select a note to read or edit
              </p>
              <p className="text-xs text-[var(--muted-foreground)]">
                Or create a new note using the button above.
              </p>
              <Button size="sm" onClick={handleCreateNote} className="gap-1.5 mt-2">
                <Plus className="h-4 w-4" strokeWidth={1.75} />
                <span>New note</span>
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
