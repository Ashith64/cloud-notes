import { useState, useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import { makeSnippet } from '@/lib/markdown'
import type { NoteDetail, NoteSummary } from '@/types/note'

export type SaveStatus = 'saved' | 'saving' | 'error'

interface UseNoteAutosaveProps {
  note: NoteDetail | null
  onNoteUpdated?: (updated: NoteDetail) => void
}

export function useNoteAutosave({ note, onNoteUpdated }: UseNoteAutosaveProps) {
  const queryClient = useQueryClient()

  const [title, setTitleState] = useState(note?.title ?? '')
  const [content, setContentState] = useState(note?.content ?? '')
  const [tags, setTagsState] = useState<string[]>(note?.tags ?? [])
  const [status, setStatus] = useState<SaveStatus>('saved')
  const [lastSaved, setLastSaved] = useState<Date | null>(note ? new Date(note.updated_at) : null)

  // Tracking refs to avoid stale closure issues in async callbacks
  const currentNoteIdRef = useRef<string | null>(note?.id ?? null)
  const titleRef = useRef(title)
  const contentRef = useRef(content)
  const tagsRef = useRef(tags)
  const versionRef = useRef(note?.version ?? 1)
  const isDirtyRef = useRef(false)
  const inFlightRef = useRef(false)
  const pendingSaveRef = useRef(false)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryCountRef = useRef(0)

  // Keep refs in sync with state
  titleRef.current = title
  contentRef.current = content
  tagsRef.current = tags

  // Optimistic update of note in query cache (updates snippet, title, updated_at)
  const updateListOptimistically = useCallback(
    (noteId: string, updatedTitle: string, updatedContent: string) => {
      const newSnippet = makeSnippet(updatedContent)
      const nowIso = new Date().toISOString()

      // Update in all 'notes' queries
      queryClient.setQueriesData<NoteSummary[]>(
        { queryKey: ['notes'] },
        (oldData) => {
          if (!oldData) return oldData
          return oldData.map((item) =>
            item.id === noteId
              ? {
                  ...item,
                  title: updatedTitle || 'Untitled',
                  snippet: newSnippet,
                  updated_at: nowIso,
                }
              : item
          )
        }
      )
    },
    [queryClient]
  )

  // Execute save call
  const performSave = useCallback(async () => {
    const targetNoteId = currentNoteIdRef.current
    if (!targetNoteId || !isDirtyRef.current) {
      return
    }

    if (inFlightRef.current) {
      pendingSaveRef.current = true
      return
    }

    inFlightRef.current = true
    setStatus('saving')

    const payloadTitle = titleRef.current
    const payloadContent = contentRef.current
    const payloadTags = tagsRef.current
    const payloadBaseVersion = versionRef.current

    try {
      const res = await api.patch<NoteDetail>(`/api/notes/${targetNoteId}`, {
        title: payloadTitle,
        content: payloadContent,
        tags: payloadTags,
        base_version: payloadBaseVersion,
      })

      inFlightRef.current = false

      // Guard against stale response if user switched notes while save was in flight
      if (currentNoteIdRef.current !== targetNoteId) {
        queryClient.invalidateQueries({ queryKey: ['notes'] })
        queryClient.invalidateQueries({ queryKey: ['note', targetNoteId] })
        return
      }

      // Success
      versionRef.current = res.version
      retryCountRef.current = 0
      setLastSaved(new Date())

      // Check if more edits occurred while request was in flight
      if (
        pendingSaveRef.current ||
        titleRef.current !== payloadTitle ||
        contentRef.current !== payloadContent ||
        tagsRef.current !== payloadTags
      ) {
        pendingSaveRef.current = false
        // Coalesce changes: trigger next save immediately
        performSave()
      } else {
        isDirtyRef.current = false
        setStatus('saved')
      }

      onNoteUpdated?.(res)

      // Sync caches
      queryClient.setQueryData(['note', targetNoteId], res)
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    } catch (err) {
      inFlightRef.current = false

      // Check for 409 conflict
      if (err instanceof ApiError && err.status === 409) {
        const conflictData = err.body as { note?: { version?: number } } | undefined
        if (conflictData?.note?.version) {
          versionRef.current = conflictData.note.version
        } else {
          versionRef.current += 1
        }
        // Retry immediately with the updated server base version
        performSave()
        return
      }

      // Transient or network error: schedule retry with backoff
      setStatus('error')
      const backoffDelay = Math.min(1000 * Math.pow(2, retryCountRef.current), 10000)
      retryCountRef.current += 1

      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      retryTimerRef.current = setTimeout(() => {
        performSave()
      }, backoffDelay)
    }
  }, [queryClient, onNoteUpdated])

  // Schedule debounced save (800ms)
  const scheduleSave = useCallback(() => {
    isDirtyRef.current = true
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = setTimeout(() => {
      performSave()
    }, 800)
  }, [performSave])

  // Flush save synchronously (e.g. before switching notes or unmounting)
  const flushSave = useCallback(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
    if (isDirtyRef.current) {
      performSave()
    }
  }, [performSave])

  // When note changes (switching notes): flush previous, reset state for new note
  useEffect(() => {
    const prevNoteId = currentNoteIdRef.current
    const newNoteId = note?.id ?? null

    if (prevNoteId && prevNoteId !== newNoteId && isDirtyRef.current) {
      // Flush edits of the previous note
      flushSave()
    }

    currentNoteIdRef.current = newNoteId
    if (note) {
      setTitleState(note.title)
      setContentState(note.content)
      setTagsState(note.tags)
      versionRef.current = note.version
      titleRef.current = note.title
      contentRef.current = note.content
      tagsRef.current = note.tags
      isDirtyRef.current = false
      setStatus('saved')
      setLastSaved(new Date(note.updated_at))
      retryCountRef.current = 0
    } else {
      setTitleState('')
      setContentState('')
      setTagsState([])
      isDirtyRef.current = false
      setStatus('saved')
      setLastSaved(null)
    }

    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    }
  }, [note?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Warn before closing tab if unsaved changes exist
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirtyRef.current) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [])

  // Change handlers
  const updateTitle = useCallback(
    (newTitle: string) => {
      setTitleState(newTitle)
      titleRef.current = newTitle
      if (currentNoteIdRef.current) {
        updateListOptimistically(currentNoteIdRef.current, newTitle, contentRef.current)
      }
      scheduleSave()
    },
    [scheduleSave, updateListOptimistically]
  )

  const updateContent = useCallback(
    (newContent: string) => {
      setContentState(newContent)
      contentRef.current = newContent
      if (currentNoteIdRef.current) {
        updateListOptimistically(currentNoteIdRef.current, titleRef.current, newContent)
      }
      scheduleSave()
    },
    [scheduleSave, updateListOptimistically]
  )

  const updateTags = useCallback(
    (newTags: string[]) => {
      setTagsState(newTags)
      tagsRef.current = newTags
      scheduleSave()
    },
    [scheduleSave]
  )

  return {
    title,
    content,
    tags,
    status,
    lastSaved,
    isDirty: isDirtyRef.current,
    updateTitle,
    updateContent,
    updateTags,
    flushSave,
    retrySave: performSave,
  }
}
