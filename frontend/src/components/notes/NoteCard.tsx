import React from 'react'
import {
  Pin,
  Star,
  Trash2,
  Archive,
  Download,
  FolderInput,
  RotateCcw,
} from 'lucide-react'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuTrigger,
} from '@/components/ui/context-menu'
import { Badge } from '@/components/ui/badge'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { NoteSummary, Notebook } from '@/types/note'

interface NoteCardProps {
  note: NoteSummary
  isSelected: boolean
  isTrashView?: boolean
  notebooks?: Notebook[]
  onSelect: (id: string) => void
  onTogglePin?: (id: string, e: React.MouseEvent) => void
  onToggleFavorite?: (id: string, isFav: boolean) => void
  onToggleArchive?: (id: string, isArchived: boolean) => void
  onDelete?: (id: string, e?: React.MouseEvent) => void
  onRestore?: (id: string) => void
  onPermanentDelete?: (id: string) => void
  onMoveNotebook?: (id: string, notebookId: number | null) => void
}

export default function NoteCard({
  note,
  isSelected,
  isTrashView = false,
  notebooks = [],
  onSelect,
  onTogglePin,
  onToggleFavorite,
  onToggleArchive,
  onDelete,
  onRestore,
  onPermanentDelete,
  onMoveNotebook,
}: NoteCardProps) {
  const handleExport = (e: React.MouseEvent) => {
    e.stopPropagation()
    const link = document.createElement('a')
    link.href = `/api/notes/${note.id}/export`
    link.download = `${note.title || 'note'}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onSelect(note.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onSelect(note.id)
            }
          }}
          data-note-id={note.id}
          className={cn(
            'group relative flex flex-col gap-1.5 rounded-xl p-3 text-left transition-colors cursor-pointer border',
            isSelected
              ? 'bg-[var(--accent-soft)] border-[var(--accent)] text-[var(--foreground)]'
              : 'bg-[var(--card)] border-transparent hover:border-[var(--border)] hover:bg-[var(--muted)]/50'
          )}
        >
          {/* Header: Title + Action Icons */}
          <div className="flex items-start justify-between gap-2">
            <h3
              className={cn(
                'text-sm font-semibold truncate',
                isSelected ? 'text-[var(--accent)] font-bold' : 'text-[var(--foreground)]'
              )}
            >
              {note.title || 'Untitled'}
            </h3>

            {/* Hover actions (Pin, Trash) or Status indicator */}
            {!isTrashView ? (
              <div className="flex items-center gap-1 shrink-0">
                {/* Pin button */}
                <button
                  type="button"
                  onClick={(e) => onTogglePin?.(note.id, e)}
                  aria-label={note.is_pinned ? 'Unpin note' : 'Pin note'}
                  className={cn(
                    'p-1 rounded-md transition-opacity',
                    note.is_pinned
                      ? 'opacity-100 text-[var(--accent)] hover:opacity-80'
                      : 'opacity-0 group-hover:opacity-100 text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                  )}
                >
                  <Pin className="h-3.5 w-3.5" fill={note.is_pinned ? 'currentColor' : 'none'} />
                </button>

                {/* Trash button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete?.(note.id, e)
                  }}
                  aria-label="Delete note"
                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--destructive)] transition-opacity"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRestore?.(note.id)
                  }}
                  aria-label="Restore note"
                  title="Restore note"
                  className="p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--accent)] transition-colors"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onPermanentDelete?.(note.id)
                  }}
                  aria-label="Delete forever"
                  title="Delete forever"
                  className="p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--destructive)] transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Two-line snippet preview */}
          <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 leading-relaxed">
            {note.snippet || 'No additional text'}
          </p>

          {/* Bottom row: tag chips + relative time */}
          <div className="mt-1 flex items-center justify-between gap-2 pt-1 text-[11px] text-[var(--muted-foreground)]">
            <div className="flex flex-wrap items-center gap-1 max-w-[70%] overflow-hidden">
              {note.tags.slice(0, 3).map((tag) => (
                <Badge
                  key={tag}
                  variant="outline"
                  className="px-1.5 py-0 text-[10px] font-normal border-[var(--border)] text-[var(--muted-foreground)]"
                >
                  #{tag}
                </Badge>
              ))}
              {note.tags.length > 3 && (
                <span className="text-[10px] text-[var(--muted-foreground)]">
                  +{note.tags.length - 3}
                </span>
              )}
            </div>

            <span className="shrink-0 font-normal">
              {formatRelativeTime(note.updated_at)}
            </span>
          </div>
        </div>
      </ContextMenuTrigger>

      {/* Right-click Context Menu */}
      <ContextMenuContent className="w-52">
        {!isTrashView ? (
          <>
            <ContextMenuItem onClick={() => onTogglePin?.(note.id, {} as React.MouseEvent)}>
              <Pin className="mr-2 h-4 w-4" />
              {note.is_pinned ? 'Unpin note' : 'Pin note'}
            </ContextMenuItem>

            <ContextMenuItem
              onClick={() => onToggleFavorite?.(note.id, !note.is_favorite)}
            >
              <Star
                className="mr-2 h-4 w-4"
                fill={note.is_favorite ? 'currentColor' : 'none'}
              />
              {note.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
            </ContextMenuItem>

            <ContextMenuSub>
              <ContextMenuSubTrigger>
                <FolderInput className="mr-2 h-4 w-4" /> Move to notebook
              </ContextMenuSubTrigger>
              <ContextMenuSubContent className="w-44">
                <ContextMenuItem onClick={() => onMoveNotebook?.(note.id, null)}>
                  <span className={!note.notebook_id ? 'font-semibold' : ''}>
                    Unfiled
                  </span>
                </ContextMenuItem>
                {notebooks.map((nb) => (
                  <ContextMenuItem
                    key={nb.id}
                    onClick={() => onMoveNotebook?.(note.id, nb.id)}
                  >
                    <span
                      className={
                        note.notebook_id === nb.id
                          ? 'font-semibold text-[var(--accent)]'
                          : ''
                      }
                    >
                      {nb.name}
                    </span>
                  </ContextMenuItem>
                ))}
              </ContextMenuSubContent>
            </ContextMenuSub>

            <ContextMenuItem
              onClick={() => onToggleArchive?.(note.id, !note.is_archived)}
            >
              <Archive className="mr-2 h-4 w-4" />
              {note.is_archived ? 'Unarchive note' : 'Archive note'}
            </ContextMenuItem>

            <ContextMenuItem onClick={handleExport}>
              <Download className="mr-2 h-4 w-4" /> Export as Markdown
            </ContextMenuItem>

            <ContextMenuSeparator />

            <ContextMenuItem
              onClick={() => onDelete?.(note.id)}
              className="text-[var(--destructive)] focus:text-[var(--destructive)]"
            >
              <Trash2 className="mr-2 h-4 w-4" /> Delete note
            </ContextMenuItem>
          </>
        ) : (
          <>
            <ContextMenuItem onClick={() => onRestore?.(note.id)}>
              <RotateCcw className="mr-2 h-4 w-4" /> Restore note
            </ContextMenuItem>
            <ContextMenuSeparator />
            <ContextMenuItem
              onClick={() => onPermanentDelete?.(note.id)}
              className="text-[var(--destructive)] focus:text-[var(--destructive)]"
            >
              <Trash2 className="mr-2 h-4 w-4" /> Delete permanently
            </ContextMenuItem>
          </>
        )}
      </ContextMenuContent>
    </ContextMenu>
  )
}
