import { useEffect, useRef } from 'react'
import { Crepe } from '@milkdown/crepe'
import { api } from '@/lib/api'

interface MilkdownEditorProps {
  initialContent: string
  noteId?: string
  readOnly?: boolean
  onChange: (markdown: string) => void
  onReady?: (crepe: Crepe) => void
}

export default function MilkdownEditor({
  initialContent,
  noteId,
  readOnly = false,
  onChange,
  onReady,
}: MilkdownEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const crepeInstanceRef = useRef<Crepe | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    let active = true
    const crepe = new Crepe({
      root: containerRef.current,
      defaultValue: initialContent || '',
      featureConfigs: {
        [Crepe.Feature.Placeholder]: {
          text: "Type '/' for commands or start writing…",
        },
        ...(noteId
          ? {
              [Crepe.Feature.ImageBlock]: {
                onUpload: async (file: File) => {
                  const formData = new FormData()
                  formData.append('file', file)
                  formData.append('note_id', noteId)
                  const res = await api.post<{ id: string; ref: string; url: string }>(
                    '/api/attachments',
                    formData
                  )
                  return res.url || `/api/attachments/${res.id}`
                },
              },
            }
          : {}),
      },
    })

    if (readOnly) {
      crepe.setReadonly(true)
    }

    crepe.on((listener) => {
      listener.markdownUpdated((_ctx, markdown) => {
        if (active) {
          onChangeRef.current(markdown)
        }
      })
    })

    crepe
      .create()
      .then(() => {
        if (!active) {
          crepe.destroy().catch(() => {})
          return
        }
        crepeInstanceRef.current = crepe
        onReady?.(crepe)
      })
      .catch((err) => {
        console.error('Error creating Crepe editor:', err)
      })

    return () => {
      active = false
      crepeInstanceRef.current = null
      crepe.destroy().catch(() => {})
    }
  }, [noteId]) // Keyed by noteId so each note gets a fresh instance

  return (
    <div
      ref={containerRef}
      className="crepe-editor-root w-full cursor-text"
      data-testid="milkdown-editor"
    />
  )
}
