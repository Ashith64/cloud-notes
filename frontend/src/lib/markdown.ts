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
