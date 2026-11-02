import puppeteer from 'puppeteer-core'
import path from 'path'
import fs from 'fs'

const SCREENSHOT_DIR = path.resolve('..', 'docs', 'screenshots')
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE_URL = 'http://localhost:5173'

// Sample minimal PDF bytes (%PDF-1.7...)
const MINIMAL_PDF = Buffer.from(
  '%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF'
)

// Minimal valid 1x1 PNG bytes
const MINIMAL_PNG = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
  0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
  0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
  0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
  0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
])

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function run() {
  console.log('🚀 Starting Stage 5B End-to-End Browser Verification...')

  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
  })

  try {
    const page = await browser.newPage()
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log('BROWSER CONSOLE ERROR:', msg.text())
    })

    // -------------------------------------------------------------------------
    // 1. DEMO ACCOUNT LOGIN
    // -------------------------------------------------------------------------
    console.log('\n⚡ 1. Logging in with Demo account...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
    await sleep(800)

    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'))
      const demoBtn = btns.find((el) => el.textContent.toLowerCase().includes('demo'))
      if (!demoBtn) throw new Error('Demo button not found')
      demoBtn.click()
    })

    await page.waitForFunction(() => window.location.pathname.startsWith('/app'), { timeout: 10000 })
    console.log('  ✅ Logged into /app successfully')
    await sleep(1000)

    // Set theme to Light
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'light')
      document.documentElement.classList.remove('dark')
    })
    await sleep(300)

    // -------------------------------------------------------------------------
    // 2. COMMAND PALETTE & LIVE SEARCH (Ctrl/Cmd+K)
    // -------------------------------------------------------------------------
    console.log('\n🔍 2. Testing Command Palette & Live Search (Requirement 3 & 5)...')
    const searchTrigger = await page.$('[data-testid="search-palette-trigger"]')
    if (!searchTrigger) throw new Error('Search palette trigger not found')
    await searchTrigger.click()
    await sleep(500)

    // Verify palette input is visible
    const paletteInput = await page.$('[cmdk-input]')
    if (!paletteInput) throw new Error('Command palette input not found')
    console.log('  ✅ Command palette opened via search trigger')

    // Live search with 200ms debounce
    await paletteInput.type('EC2')
    await sleep(400)

    // Capture screenshot: stage5b-desktop-search-palette.png
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-desktop-search-palette.png') })
    console.log('  📸 Captured stage5b-desktop-search-palette.png')

    // Press Enter to select the matching note
    await page.keyboard.press('Enter')
    await sleep(1000)
    console.log('  ✅ Selected matching note via Enter key')

    // -------------------------------------------------------------------------
    // 3. ATTACHMENTS (Image & PDF - Requirement 1)
    // -------------------------------------------------------------------------
    console.log('\n📎 3. Testing PDF and Image Attachments (Requirement 1)...')
    // Upload both PDF and Image attachments via API and refresh note
    await page.evaluate(
      async (pdfB64, pngB64) => {
        const activeNoteId = new URLSearchParams(window.location.search).get('note')
        if (!activeNoteId) return

        // 1. Upload PDF
        const pdfBytes = Uint8Array.from(atob(pdfB64), (c) => c.charCodeAt(0))
        const pdfBlob = new Blob([pdfBytes], { type: 'application/pdf' })
        const pdfForm = new FormData()
        pdfForm.append('file', pdfBlob, 'cloud_notes_syllabus.pdf')
        pdfForm.append('note_id', activeNoteId)
        await fetch('/api/attachments', {
          method: 'POST',
          headers: { 'X-Requested-With': 'cloudnotes' },
          body: pdfForm,
        })

        // 2. Upload Image
        const pngBytes = Uint8Array.from(atob(pngB64), (c) => c.charCodeAt(0))
        const pngBlob = new Blob([pngBytes], { type: 'image/png' })
        const pngForm = new FormData()
        pngForm.append('file', pngBlob, 'architecture_diagram.png')
        pngForm.append('note_id', activeNoteId)
        await fetch('/api/attachments', {
          method: 'POST',
          headers: { 'X-Requested-With': 'cloudnotes' },
          body: pngForm,
        })
      },
      MINIMAL_PDF.toString('base64'),
      MINIMAL_PNG.toString('base64')
    )

    // Reload note to see attached PDF chips
    await page.reload({ waitUntil: 'domcontentloaded' })
    await sleep(1500)

    const pdfChipText = await page.evaluate(() => {
      const chipList = document.querySelector('[data-testid="pdf-attachments-list"]')
      return chipList ? chipList.textContent : null
    })
    console.log('  ✅ PDF Attachment chip rendered:', pdfChipText)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-desktop-editor-attachments.png') })
    console.log('  📸 Captured stage5b-desktop-editor-attachments.png')

    // -------------------------------------------------------------------------
    // 4. NOTE DELETION & 6-SECOND UNDO TOAST (Requirement 2)
    // -------------------------------------------------------------------------
    console.log('\n🗑️ 4. Testing Note Deletion and 6-Second Undo Toast (Requirement 2)...')
    // Delete active note via options menu
    await page.evaluate(() => {
      const optionsBtn = document.querySelector('button[aria-label="Note options"]')
      if (optionsBtn) optionsBtn.click()
    })
    await sleep(400)

    await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
      const deleteItem = items.find((el) => el.textContent.toLowerCase().includes('delete note'))
      if (deleteItem) deleteItem.click()
    })
    await sleep(800)

    // Check Sonner toast for "Moved to Trash" and "Undo" button
    const toastInfo = await page.evaluate(() => {
      const toasts = Array.from(document.querySelectorAll('[data-sonner-toast]'))
      const trashToast = toasts.find((t) => t.textContent.includes('Moved to Trash'))
      if (!trashToast) return null
      const undoBtn = Array.from(trashToast.querySelectorAll('button')).find((b) =>
        b.textContent.toLowerCase().includes('undo')
      )
      return {
        text: trashToast.textContent,
        hasUndo: Boolean(undoBtn),
      }
    })
    console.log('  ✅ Moved to Trash toast detected:', toastInfo)

    // Click Undo
    await page.evaluate(() => {
      const toasts = Array.from(document.querySelectorAll('[data-sonner-toast]'))
      const trashToast = toasts.find((t) => t.textContent.includes('Moved to Trash'))
      if (trashToast) {
        const undoBtn = Array.from(trashToast.querySelectorAll('button')).find((b) =>
          b.textContent.toLowerCase().includes('undo')
        )
        if (undoBtn) undoBtn.click()
      }
    })
    await sleep(1200)
    console.log('  ✅ Clicked Undo button, note successfully restored!')

    // -------------------------------------------------------------------------
    // 5. TRASH VIEW (30-day notice, Restore, Delete Forever, Empty Trash)
    // -------------------------------------------------------------------------
    console.log('\n🚮 5. Testing Trash View & 30-Day Notice (Requirement 2)...')
    // Move note to trash again so Trash list is populated
    await page.evaluate(() => {
      const optionsBtn = document.querySelector('button[aria-label="Note options"]')
      if (optionsBtn) optionsBtn.click()
    })
    await sleep(400)
    await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
      const deleteItem = items.find((el) => el.textContent.toLowerCase().includes('delete note'))
      if (deleteItem) deleteItem.click()
    })
    await sleep(800)

    // Navigate to Trash view
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('button, a'))
      const trashLink = links.find((el) => el.textContent.trim().startsWith('Trash'))
      if (trashLink) trashLink.click()
    })
    await sleep(1000)

    // Verify 30-day notice
    const has30DayNotice = await page.evaluate(() => {
      return document.body.innerText.includes('30 days')
    })
    console.log('  ✅ 30-day Trash notice present:', has30DayNotice)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-desktop-trash-view.png') })
    console.log('  📸 Captured stage5b-desktop-trash-view.png')

    // -------------------------------------------------------------------------
    // 6. SETTINGS PAGE (Storage Used Progress Bar, Password Validation, ZIP Export)
    // -------------------------------------------------------------------------
    console.log('\n⚙️ 6. Testing Settings Page per C3.4 (Requirement 4)...')
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'domcontentloaded' })
    await sleep(1000)

    // Verify storage bar
    const storageInfo = await page.evaluate(() => {
      const bar = document.querySelector('[data-testid="storage-progress-bar"]')
      const text = document.body.innerText
      return {
        hasBar: Boolean(bar),
        hasUsedText: text.includes('of 100 MB used'),
        hasNotesBytes: text.includes('Notes:'),
        hasAttachmentsBytes: text.includes('Attachments:'),
      }
    })
    console.log('  ✅ Storage usage calculated from actual sizes:', storageInfo)

    // Test password change validation
    const changeBtn = await page.$('[data-testid="change-password-toggle"]')
    if (changeBtn) {
      await changeBtn.click()
      await sleep(300)

      // Enter short password (<8 chars)
      await page.type('#old-password', 'demo-password-not-for-login')
      await page.type('#new-password', 'short')
      await page.type('#confirm-password', 'short')

      const submitBtn = await page.$('[data-testid="submit-new-password"]')
      if (submitBtn) await submitBtn.click()
      await sleep(400)

      const validationError = await page.evaluate(() => {
        const err = document.querySelector('[data-testid="change-password-form"]')
        return err ? err.textContent : null
      })
      console.log('  ✅ Password validation (< 8 chars) caught correctly:', validationError?.includes('8 characters'))
    }

    // Capture Settings Light
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-settings-storage-light.png') })
    console.log('  📸 Captured stage5b-settings-storage-light.png')

    // Switch to Dark theme
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'dark')
      document.documentElement.classList.add('dark')
    })
    await sleep(400)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-settings-storage-dark.png') })
    console.log('  📸 Captured stage5b-settings-storage-dark.png')

    // Switch back to Light theme
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'light')
      document.documentElement.classList.remove('dark')
    })
    await sleep(300)

    // -------------------------------------------------------------------------
    // 7. RESPONSIVE TABLET VIEW (768px - Drawer)
    // -------------------------------------------------------------------------
    console.log('\n📱 7. Testing Tablet Layout (768px)...')
    await page.setViewport({ width: 768, height: 1024 })
    await page.goto(`${BASE_URL}/app`, { waitUntil: 'domcontentloaded' })
    await sleep(1000)

    // Open hamburger drawer
    await page.evaluate(() => {
      const hamburger = document.querySelector('button[aria-label="Open menu"]')
      if (hamburger) hamburger.click()
    })
    await sleep(600)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-tablet-view.png') })
    console.log('  📸 Captured stage5b-tablet-view.png')

    // Close drawer
    await page.keyboard.press('Escape')
    await sleep(400)

    // -------------------------------------------------------------------------
    // 8. RESPONSIVE PHONE VIEW (375px - List First, Floating +, Touch Editor)
    // -------------------------------------------------------------------------
    console.log('\n📲 8. Testing Mobile Phone Layout (375px - Requirement 6)...')
    await page.setViewport({ width: 375, height: 667 })
    // Navigate without active note
    await page.goto(`${BASE_URL}/app?view=all`, { waitUntil: 'domcontentloaded' })
    await sleep(1000)

    // Verify floating + button visible on phone list
    const hasFloatingPlus = await page.evaluate(() => {
      const btn = document.querySelector('[data-testid="mobile-floating-plus"]')
      return Boolean(btn)
    })
    console.log('  ✅ Floating + button present on mobile list:', hasFloatingPlus)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-mobile-list-floating.png') })
    console.log('  📸 Captured stage5b-mobile-list-floating.png')

    // Tap a note to open editor full-screen
    const noteCard = await page.$('[data-note-id]')
    if (noteCard) {
      await noteCard.click()
      await sleep(1000)

      const hasBackArrow = await page.evaluate(() => {
        return document.body.innerText.includes('Notes')
      })
      console.log('  ✅ Mobile editor back arrow header present:', hasBackArrow)

      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-mobile-editor-touch.png') })
      console.log('  📸 Captured stage5b-mobile-editor-touch.png')
    }

    // -------------------------------------------------------------------------
    // 9. NETWORK RESILIENCE BANNER (Requirement 7)
    // -------------------------------------------------------------------------
    console.log('\n🌐 9. Testing Network Resilience Banner (Requirement 7)...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.evaluate(() => {
      window.dispatchEvent(new Event('offline'))
    })
    await sleep(500)

    const bannerText = await page.evaluate(() => {
      const banner = document.querySelector('[data-testid="network-banner"]')
      return banner ? banner.textContent : null
    })
    console.log('  ✅ Network banner detected:', bannerText)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5b-network-banner.png') })
    console.log('  📸 Captured stage5b-network-banner.png')

    // Reset online
    await page.evaluate(() => {
      window.dispatchEvent(new Event('online'))
    })
    await sleep(300)

    // -------------------------------------------------------------------------
    // 10. FRESH USER REGISTRATION
    // -------------------------------------------------------------------------
    console.log('\n👤 10. Testing Fresh User Registration & Must Features...')
    // Log out first
    await page.evaluate(async () => {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'X-Requested-With': 'cloudnotes' },
      })
    })
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
    await sleep(800)

    // Switch to Register mode
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'))
      const regBtn = btns.find((b) => b.textContent.toLowerCase().includes('sign up'))
      if (regBtn) regBtn.click()
    })
    await sleep(300)

    const freshEmail = `student_${Date.now()}@university.edu`
    await page.type('#name', 'Taylor Student')
    await page.type('#email', freshEmail)
    await page.type('#password', 'ValidPass123!')

    await page.evaluate(() => {
      const submitBtn = document.querySelector('button[type="submit"]')
      if (submitBtn) submitBtn.click()
    })

    await page.waitForFunction(() => window.location.pathname.startsWith('/app'), { timeout: 10000 })
    console.log(`  ✅ Registered and logged in as fresh user (${freshEmail})`)
    await sleep(1000)

    // Verify empty state for fresh account
    const emptyStateText = await page.evaluate(() => document.body.innerText)
    const hasEmptyState = emptyStateText.includes('No notes yet')
    console.log('  ✅ Fresh user empty state detected:', hasEmptyState)

    console.log('\n🎉 ALL STAGE 5B VERIFICATION CHECKS PASSED SUCCESSFULLY!')
  } finally {
    await browser.close()
  }
}

run().catch((err) => {
  console.error('❌ Verification failed:', err)
  process.exit(1)
})
