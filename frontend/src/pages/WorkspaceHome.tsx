import { FileText } from 'lucide-react'

export default function WorkspaceHome() {
  return (
    <div className="flex flex-1">
      {/* Note list pane — hidden below 640px when no note selected */}
      <div className="w-[340px] flex-shrink-0 border-r border-[var(--border)] bg-[var(--surface)] hidden sm:flex flex-col">
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">All Notes</h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center p-8 space-y-3">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--accent-soft)]">
              <FileText className="h-6 w-6 text-[var(--accent)]" strokeWidth={1.75} />
            </div>
            <p className="text-sm font-medium text-[var(--foreground)]">No notes yet</p>
            <p className="text-xs text-[var(--muted-foreground)]">Create your first note to get started.</p>
          </div>
        </div>
      </div>

      {/* Editor / empty state */}
      <div className="flex-1 flex items-center justify-center bg-[var(--background)]">
        <div className="text-center p-8 space-y-3 max-w-xs">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--muted)]">
            <FileText className="h-6 w-6 text-[var(--muted-foreground)]" strokeWidth={1.75} />
          </div>
          <p className="text-sm font-medium text-[var(--foreground)]">Select a note to read or edit</p>
          <p className="text-xs text-[var(--muted-foreground)]">Or create a new note using the button above.</p>
        </div>
      </div>
    </div>
  )
}
