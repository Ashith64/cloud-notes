/**
 * Markdown stripping utility for client-side optimistic snippets.
 * Mirrors backend/app/utils.py logic.
 */

const MD_PATTERNS: [RegExp, string][] = [
  [/```[\s\S]*?```/g, ''],
  [/`([^`]+)`/g, '$1'],
  [/!\[([^\]]*)\]\([^)]+\)/g, ''],
  [/\[([^\]]+)\]\([^)]+\)/g, '$1'],
  [/^#{1,6}\s+/gm, ''],
  [/^[>\s]*>\s?/gm, ''],
  [/^[-*+]\s+/gm, ''],
  [/^\d+\.\s+/gm, ''],
  [/^-{3,}$/gm, ''],
  [/\*{1,3}([^*]+)\*{1,3}/g, '$1'],
  [/_{1,3}([^_]+)_{1,3}/g, '$1'],
  [/~~([^~]+)~~/g, '$1'],
  [/<[^>]+>/g, ''],
  [/^\||\|$/gm, ''],
  [/\|/g, ' '],
  [/:?-{3,}:?/g, ''],
]

export function stripMarkdown(text: string): string {
  let plain = text
  for (const [pattern, replacement] of MD_PATTERNS) {
    plain = plain.replace(pattern, replacement)
  }
  return plain.replace(/\n{2,}/g, '\n').trim()
}

export function makeSnippet(body: string, maxLen = 200): string {
  const plain = stripMarkdown(body)
  if (plain.length <= maxLen) return plain
  return plain.slice(0, maxLen)
}

/**
 * Ensures Markdown references to attachments always use the stable 'attachments/<id>.<ext>' format
 * and never raw API paths or temporary blob URLs.
 */
export function toStorageMarkdown(content: string): string {
  if (!content) return ''
  return content.replace(
    /!\[([^\]]*)\]\((?:https?:\/\/[^/]+)?\/api\/attachments\/([a-zA-Z0-9_-]+)\)/g,
    '![$1](attachments/$2.png)'
  )
}

/**
 * Maps a stored attachment reference (attachments/<id>.<ext>) to the browser display URL (/api/attachments/<id>).
 */
export function resolveAttachmentDomUrl(url: string): string {
  if (!url) return ''
  const match = url.match(/(?:^\.?\/?attachments\/|^attachments\/)([a-zA-Z0-9_-]+)(?:\.[a-zA-Z0-9]+)?/)
  if (match) {
    return `/api/attachments/${match[1]}`
  }
  return url
}
