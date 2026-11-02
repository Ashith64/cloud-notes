export interface NoteSummary {
  id: string
  title: string
  snippet: string
  notebook_id: number | null
  tags: string[]
  is_pinned: boolean
  is_favorite: boolean
  is_archived: boolean
  deleted_at: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface NoteDetail extends NoteSummary {
  content: string
}

export interface Notebook {
  id: number
  name: string
  created_at: string | null
}

export interface TagCount {
  name: string
  count: number
}

export type ViewFilter = 'all' | 'favorites' | 'archive' | 'trash'
