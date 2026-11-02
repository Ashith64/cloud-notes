import { useEffect, useRef } from 'react'
import { Crepe } from '@milkdown/crepe'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { resolveAttachmentDomUrl, toStorageMarkdown } from '@/lib/markdown'

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
                  const toastId = toast.loading(`Uploading ${file.name || 'image'}…`)
                  try {
                    const formData = new FormData()
                    formData.append('file', file)
                    formData.append('note_id', noteId)
                    const res = await api.post<{ id: string; ref: string; url: string }>(
                      '/api/attachments',
                      formData
                    )
                    toast.success('Image uploaded', { id: toastId })
                    // Store the stable reference in markdown: attachments/<id>.<ext>
                    return res.ref || `attachments/${res.id}.png`
                  } catch (err: any) {
                    toast.error(err?.message || 'Failed to upload image', { id: toastId })
                    throw err
                  }
                },
                proxyDomURL: (url: string) => {
                  return resolveAttachmentDomUrl(url)
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
          onChangeRef.current(toStorageMarkdown(markdown))
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
