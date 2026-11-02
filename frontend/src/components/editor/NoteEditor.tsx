import { useState, useRef, useEffect } from 'react'
import {
  MoreHorizontal,
  Download,
  FolderInput,
  Archive,
  Trash2,
  Plus,
  X,
  RotateCcw,
  Check,
  Loader2,
  Paperclip,
  FileText,
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import MilkdownEditor from './MilkdownEditor'
import { useNoteAutosave } from '@/hooks/useNoteAutosave'
import { api } from '@/lib/api'
import { formatBytes } from '@/lib/utils'
import type { NoteDetail, Notebook } from '@/types/note'

interface NoteEditorProps {
  note: NoteDetail
  autoFocusTitle?: boolean
  onNoteUpdated?: (updated: NoteDetail) => void
  onDeleteNote?: (id: string) => void
  onRestoreNote?: (id: string) => void
  onPermanentDeleteNote?: (id: string) => void
  onToggleArchive?: (id: string, isArchived: boolean) => void
  onMoveNotebook?: (id: string, notebookId: number | null) => void
}

export default function NoteEditor({
  note,
  autoFocusTitle = false,
  onNoteUpdated,
  onDeleteNote,
  onRestoreNote,
  onPermanentDeleteNote,
  onToggleArchive,
  onMoveNotebook,
}: NoteEditorProps) {
  const queryClient = useQueryClient()
  const titleInputRef = useRef<HTMLInputElement>(null)
  const pdfInputRef = useRef<HTMLInputElement>(null)
  const [isAddingTag, setIsAddingTag] = useState(false)
  const [newTagInput, setNewTagInput] = useState('')

  const isTrashed = Boolean(note.deleted_at)

  const {
    title,
    tags,
    status,
    lastSaved,
    updateTitle,
    updateContent,
    updateTags,
    retrySave,
  } = useNoteAutosave({ note, onNoteUpdated })

  // Query user's notebooks for Move to Notebook submenu
  const { data: notebooks = [] } = useQuery<Notebook[]>({
    queryKey: ['notebooks'],
    queryFn: () => api.get<Notebook[]>('/api/notebooks'),
  })

  // Autofocus title on new note creation
  useEffect(() => {
    if (autoFocusTitle && titleInputRef.current) {
      titleInputRef.current.focus()
      titleInputRef.current.select()
    }
  }, [autoFocusTitle, note.id])

  // Handle adding tag
  const handleAddTagSubmit = () => {
    const cleanTag = newTagInput.trim().toLowerCase().slice(0, 30)
    if (cleanTag && !tags.includes(cleanTag) && tags.length < 10) {
      updateTags([...tags, cleanTag])
    }
    setNewTagInput('')
    setIsAddingTag(false)
  }

  // Handle removing tag
  const handleRemoveTag = (tagToRemove: string) => {
    updateTags(tags.filter((t) => t !== tagToRemove))
  }

  // Handle PDF upload
  const handlePdfUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    const toastId = toast.loading(`Attaching ${file.name}…`)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('note_id', note.id)
      await api.post('/api/attachments', formData)
      await queryClient.invalidateQueries({ queryKey: ['note', note.id] })
      toast.success('PDF attached', { id: toastId })
    } catch (err: any) {
      toast.error(err?.message || 'Failed to attach PDF', { id: toastId })
    }
  }

  // Handle export
  const handleExport = () => {
    const link = document.createElement('a')
    link.href = `/api/notes/${note.id}/export`
    link.download = `${note.title || 'note'}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const pdfAttachments = (note.attachments || []).filter(
    (a) => a.content_type === 'application/pdf' || a.filename.toLowerCase().endsWith('.pdf')
  )

  return (
    <div
      key={note.id}
      className="fade-in-120 flex flex-1 flex-col h-full overflow-hidden bg-[var(--surface)] text-[var(--foreground)]"
      data-testid="note-editor"
    >
      {/* Hidden PDF upload input */}
      <input
        ref={pdfInputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden"
        onChange={handlePdfUpload}
      />

      {/* Trash Warning Banner if Note is in Trash */}
      {isTrashed && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2.5 flex items-center justify-between text-xs text-amber-900 dark:text-amber-200 shrink-0">
          <span className="flex items-center gap-1.5 font-medium">
            <Trash2 className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            This note is in Trash. Items are removed after 30 days.
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/20"
              onClick={() => onRestoreNote?.(note.id)}
            >
              <RotateCcw className="h-3 w-3 mr-1" /> Restore
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="h-7 text-xs"
              onClick={() => onPermanentDeleteNote?.(note.id)}
            >
              Delete forever
            </Button>
          </div>
        </div>
      )}

      {/* Editor Content Area */}
      <div className="flex-1 overflow-y-auto px-6 pt-8 pb-4">
        <div className="max-w-[720px] mx-auto space-y-4">
          {/* Big Borderless Title Input */}
          <input
            ref={titleInputRef}
            type="text"
            disabled={isTrashed}
            value={title}
            onChange={(e) => updateTitle(e.target.value)}
            placeholder="Untitled"
            className="w-full bg-transparent text-[32px] font-bold leading-tight border-none outline-none text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:ring-0 p-0 disabled:opacity-70"
            data-testid="note-title-input"
          />

          {/* Tag Chips Row with Inline Add Field + Attach PDF button */}
          <div className="flex flex-wrap items-center gap-1.5 py-1">
            {tags.map((tag) => (
              <Badge
                key={tag}
                variant="secondary"
                className="gap-1 px-2 py-0.5 text-xs font-normal bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                <span>#{tag}</span>
                {!isTrashed && (
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="rounded-full hover:bg-[var(--border)] p-0.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                    aria-label={`Remove tag ${tag}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </Badge>
            ))}

            {!isTrashed && (
              <>
                {isAddingTag ? (
                  <div className="flex items-center gap-1">
                    <input
                      type="text"
                      value={newTagInput}
                      onChange={(e) => setNewTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleAddTagSubmit()
                        } else if (e.key === 'Escape') {
                          setIsAddingTag(false)
                          setNewTagInput('')
                        }
                      }}
                      onBlur={handleAddTagSubmit}
                      placeholder="tag name"
                      autoFocus
                      className="h-6 w-24 rounded border border-[var(--border)] bg-[var(--background)] px-1.5 text-xs text-[var(--foreground)] outline-none focus:border-[var(--accent)]"
                    />
                  </div>
                ) : (
                  tags.length < 10 && (
                    <button
                      type="button"
                      onClick={() => setIsAddingTag(true)}
                      className="flex items-center gap-1 rounded-md px-2 py-0.5 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                    >
                      <Plus className="h-3 w-3" />
                      <span>tag</span>
                    </button>
                  )
                )}

                {/* Attach PDF button */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => pdfInputRef.current?.click()}
                  className="h-6 text-xs gap-1 rounded-md px-2 border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  aria-label="Attach PDF"
                >
                  <Paperclip className="h-3.5 w-3.5" />
                  <span>Attach PDF</span>
                </Button>
              </>
            )}
          </div>

          {/* Milkdown Crepe Editor */}
          <div className="pt-2">
            <MilkdownEditor
              key={note.id}
              noteId={note.id}
              initialContent={note.content}
              readOnly={isTrashed}
              onChange={updateContent}
            />
          </div>

          {/* PDF Attachments Chips under the editor */}
          {pdfAttachments.length > 0 && (
            <div className="mt-8 pt-4 border-t border-[var(--border)]" data-testid="pdf-attachments-list">
              <p className="text-xs font-semibold text-[var(--muted-foreground)] mb-2.5">
                Attached Files ({pdfAttachments.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {pdfAttachments.map((att) => (
                  <a
                    key={att.id}
                    href={att.url}
                    download={att.filename}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs text-[var(--foreground)] hover:border-[var(--accent)] hover:bg-[var(--accent-soft)] transition-colors group"
                  >
                    <FileText className="h-4 w-4 text-[var(--accent)] shrink-0" />
                    <span className="font-medium max-w-[200px] truncate">{att.filename}</span>
                    <span className="text-[10px] text-[var(--muted-foreground)]">
                      ({formatBytes(att.size_bytes)})
                    </span>
                    <Download className="h-3 w-3 text-[var(--muted-foreground)] group-hover:text-[var(--accent)] ml-1" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quiet Footer */}
      <footer className="flex h-10 shrink-0 items-center justify-between border-t border-[var(--border)] bg-[var(--surface)] px-6 text-xs text-[var(--muted-foreground)]">
        {/* Left: Save status */}
        <div className="flex items-center gap-2">
          {!isTrashed && (
            <>
              {status === 'saving' && (
                <span className="flex items-center gap-1.5 text-[var(--muted-foreground)]" data-testid="save-status-saving">
                  <Loader2 className="h-3 w-3 animate-spin text-[var(--accent)]" />
                  <span>Saving…</span>
                </span>
              )}
              {status === 'saved' && (
                <span className="flex items-center gap-1.5 text-[var(--muted-foreground)]" data-testid="save-status-saved">
                  <Check className="h-3 w-3 text-[var(--success)]" />
                  <span>{lastSaved ? 'Saved just now' : 'Saved'}</span>
                </span>
              )}
              {status === 'error' && (
                <span className="flex items-center gap-1.5 text-[var(--destructive)]" data-testid="save-status-error">
                  <span>Not saved yet</span>
                  <button
                    onClick={retrySave}
                    className="ml-1 inline-flex items-center gap-1 underline underline-offset-2 hover:opacity-80"
                  >
                    <RotateCcw className="h-3 w-3" /> Retry
                  </button>
                </span>
              )}
            </>
          )}
        </div>

        {/* Right: Actions ... Menu */}
        <div className="flex items-center gap-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                aria-label="Note options"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={handleExport}>
                <Download className="mr-2 h-4 w-4" /> Download as Markdown
              </DropdownMenuItem>

              {!isTrashed && (
                <>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      <FolderInput className="mr-2 h-4 w-4" /> Move to notebook
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent className="w-44">
                      <DropdownMenuItem onClick={() => onMoveNotebook?.(note.id, null)}>
                        <span className={!note.notebook_id ? 'font-semibold' : ''}>
                          Unfiled
                        </span>
                      </DropdownMenuItem>
                      {notebooks.map((nb) => (
                        <DropdownMenuItem
                          key={nb.id}
                          onClick={() => onMoveNotebook?.(note.id, nb.id)}
                        >
                          <span className={note.notebook_id === nb.id ? 'font-semibold text-[var(--accent)]' : ''}>
                            {nb.name}
                          </span>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>

                  <DropdownMenuItem
                    onClick={() => onToggleArchive?.(note.id, !note.is_archived)}
                  >
                    <Archive className="mr-2 h-4 w-4" />
                    {note.is_archived ? 'Unarchive note' : 'Archive note'}
                  </DropdownMenuItem>

                  <DropdownMenuSeparator />

                  <DropdownMenuItem
                    onClick={() => onDeleteNote?.(note.id)}
                    className="text-[var(--destructive)] focus:text-[var(--destructive)]"
                  >
                    <Trash2 className="mr-2 h-4 w-4" /> Delete note
                  </DropdownMenuItem>
                </>
              )}

              {isTrashed && (
                <>
                  <DropdownMenuItem onClick={() => onRestoreNote?.(note.id)}>
                    <RotateCcw className="mr-2 h-4 w-4" /> Restore note
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => onPermanentDeleteNote?.(note.id)}
                    className="text-[var(--destructive)] focus:text-[var(--destructive)]"
                  >
                    <Trash2 className="mr-2 h-4 w-4" /> Delete forever
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </footer>
    </div>
  )
}
