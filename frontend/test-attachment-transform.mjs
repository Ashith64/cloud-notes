import assert from 'node:assert'
import { toStorageMarkdown, resolveAttachmentDomUrl } from './src/lib/markdown.ts'

console.log('Testing Attachment URL transforms...')

// 1. resolveAttachmentDomUrl
assert.strictEqual(
  resolveAttachmentDomUrl('attachments/12345.png'),
  '/api/attachments/12345'
)
assert.strictEqual(
  resolveAttachmentDomUrl('./attachments/abc-def.pdf'),
  '/api/attachments/abc-def'
)
assert.strictEqual(
  resolveAttachmentDomUrl('https://example.com/other.png'),
  'https://example.com/other.png'
)

// 2. toStorageMarkdown
assert.strictEqual(
  toStorageMarkdown('![photo](http://localhost:8000/api/attachments/abc)'),
  '![photo](attachments/abc.png)'
)
assert.strictEqual(
  toStorageMarkdown('![photo](/api/attachments/xyz-123)'),
  '![photo](attachments/xyz-123.png)'
)
assert.strictEqual(
  toStorageMarkdown('![photo](attachments/stable-id.png)'),
  '![photo](attachments/stable-id.png)'
)

console.log('All attachment transform assertions passed successfully!')
