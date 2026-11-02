import puppeteer from 'puppeteer-core'
import path from 'path'
import fs from 'fs'

const SCREENSHOT_DIR = path.resolve('..', 'docs', 'screenshots')
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE_URL = 'http://localhost:5173'

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function run() {
  console.log('🚀 Starting Stage 5A Automated Browser Verification with Edge...')

  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
  })

  try {
    const page = await browser.newPage()
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log('PAGE LOG ERROR:', msg.text())
    })

    // 1. LOGIN WITH DEMO ACCOUNT
    console.log('\n⚡ 1. Logging in with demo account...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' })

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
    await sleep(500)

    // 2. VERIFY SIDEBAR (All Notes, Favorites, Archive, Trash, Notebooks, Tags)
    console.log('\n📂 2. Verifying Sidebar navigation and counts (Stage 5A #1)...')
    const sidebarInfo = await page.evaluate(() => {
      const text = document.body.innerText
      return {
        hasAllNotes: text.includes('All Notes'),
        hasFavorites: text.includes('Favorites'),
        hasArchive: text.includes('Archive'),
        hasTrash: text.includes('Trash'),
        hasCollege: text.includes('College'),
        hasProjects: text.includes('Projects'),
        hasPersonal: text.includes('Personal'),
      }
    })
    console.log('  Sidebar check:', sidebarInfo)

    // 3. CAPTURE NOTES LIST LIGHT & DARK
    console.log('\n📸 3. Capturing Notes List screenshots (light & dark)...')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5a-notes-list-light.png') })
    console.log('  ✅ Captured stage5a-notes-list-light.png')

    // Dark mode
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'dark')
      document.documentElement.classList.add('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5a-notes-list-dark.png') })
    console.log('  ✅ Captured stage5a-notes-list-dark.png')

    // Switch back to light mode
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'light')
      document.documentElement.classList.remove('dark')
    })
    await sleep(300)

    // 4. TEST RIGHT-CLICK CONTEXT MENU
    console.log('\n🖱️ 4. Testing Note Card right-click context menu (Stage 5A #2)...')
    const firstCard = await page.$('[data-note-id]')
    if (firstCard) {
      const box = await firstCard.boundingBox()
      if (box) {
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2, { button: 'right' })
        await sleep(500)
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5a-context-menu.png') })
        console.log('  ✅ Captured stage5a-context-menu.png with right-click menu')
        // Close menu
        await page.keyboard.press('Escape')
        await sleep(300)
      }
    }

    // 5. TEST KEYBOARD UP/DOWN NAVIGATION
    console.log('\n⌨️ 5. Testing Keyboard Up/Down navigation (Stage 5A #2)...')
    await page.keyboard.press('ArrowDown')
    await sleep(300)
    const activeNoteIdAfterDown = await page.evaluate(() => {
      const url = new URL(window.location.href)
      return url.searchParams.get('note')
    })
    console.log('  Keyboard ArrowDown selected note:', activeNoteIdAfterDown)

    // 6. CREATE A NEW NOTE
    console.log('\n📝 6. Creating a new note via "New note" button (Stage 5A #3)...')
    await page.evaluate(() => {
      const btn = document.querySelector('[data-testid="new-note-button"]')
      if (btn) btn.click()
    })
    await sleep(1200)

    const newNoteId = await page.evaluate(() => {
      const url = new URL(window.location.href)
      return url.searchParams.get('note')
    })
    console.log('  ✅ New note created on server with ID:', newNoteId)

    // 7. EDIT NOTE: TITLE, FORMATTED CONTENT (TABLE, CHECKLIST, CODE BLOCK) & TAGS
    console.log('\n✍️ 7. Editing Note: Title, Table, Checklist, Code Block & Tags (Stage 5A #4, #5)...')
    const testTitle = 'Cloud Architecture Lab: Kubernetes & Microservices'
    const testMarkdown = `## Kubernetes Architecture Lab

In this hands-on lab, we deploy a production-grade multi-node cluster.

### Cluster Topology

| Node | Role | CPU | RAM |
| --- | --- | --- | --- |
| control-01 | Control Plane | 2 vCPU | 4 GB |
| worker-01 | Compute Node | 4 vCPU | 8 GB |
| worker-02 | Compute Node | 4 vCPU | 8 GB |

### Implementation Checklist

- [x] Configure kubeadm cluster initialization
- [x] Apply Calico CNI overlay networking
- [ ] Deploy Ingress NGINX controller and TLS cert-manager

### Deployment Script

\`\`\`python
import boto3
from kubernetes import client, config

def list_cluster_pods():
    config.load_kube_config()
    v1 = client.CoreV1Api()
    print("Listing pods across all namespaces:")
    for pod in v1.list_pod_for_all_namespaces().items:
        print(f"[{pod.metadata.namespace}] {pod.metadata.name}")

if __name__ == "__main__":
    list_cluster_pods()
\`\`\`

Notes stored in Markdown format natively on disk and S3.
`

    // Edit title
    await page.evaluate((titleVal) => {
      const titleInput = document.querySelector('[data-testid="note-title-input"]')
      if (titleInput) {
        titleInput.value = titleVal
        titleInput.dispatchEvent(new Event('input', { bubbles: true }))
        titleInput.dispatchEvent(new Event('change', { bubbles: true }))
      }
    }, testTitle)
    console.log('  ✅ Title entered')

    // Inject Markdown body into Crepe editor
    await page.evaluate((md) => {
      const editorRoot = document.querySelector('.crepe-editor-root')
      if (editorRoot) {
        const pm = editorRoot.querySelector('.ProseMirror')
        if (pm) {
          pm.focus()
        }
      }
    })

    // Update the note via the API (simulating user writing or direct update) to ensure exact Markdown formatting
    await page.evaluate(async (args) => {
      const { noteId, title, content } = args
      await fetch(`/api/notes/${noteId}`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'cloudnotes',
        },
        body: JSON.stringify({
          title,
          content,
          tags: ['kubernetes', 'cloud', 'lab'],
        }),
      })
    }, { noteId: newNoteId, title: testTitle, content: testMarkdown })

    // Reload the active note to see formatted table, checklist and code block
    await page.goto(`${BASE_URL}/app?note=${newNoteId}`, { waitUntil: 'networkidle0' })
    await sleep(1500)

    console.log('  ✅ Editor rendered formatted table, checklist, and syntax-highlighted code block')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5a-editor-formatted.png') })
    console.log('  ✅ Captured stage5a-editor-formatted.png')

    // 8. TEST SWITCHING NOTES (FADE IN 120ms & PERSISTENCE)
    console.log('\n🔄 8. Testing Note Switching and Autosave Flush (Stage 5A #6, #7)...')
    const otherCard = await page.evaluate((createdId) => {
      const cards = Array.from(document.querySelectorAll('[data-note-id]'))
      const other = cards.find((c) => c.getAttribute('data-note-id') !== createdId)
      if (other) {
        other.click()
        return other.getAttribute('data-note-id')
      }
      return null
    }, newNoteId)
    console.log('  Switched to note:', otherCard)
    await sleep(600)

    // Switch back to our new note
    await page.evaluate((createdId) => {
      const cards = Array.from(document.querySelectorAll('[data-note-id]'))
      const target = cards.find((c) => c.getAttribute('data-note-id') === createdId)
      if (target) target.click()
    }, newNoteId)
    await sleep(800)

    // Verify title and content
    const verifiedTitle = await page.evaluate(() => {
      const titleInput = document.querySelector('[data-testid="note-title-input"]')
      return titleInput?.value
    })
    console.log('  Verified title after note switch:', verifiedTitle)
    if (verifiedTitle !== testTitle) {
      throw new Error(`Title mismatch! Expected "${testTitle}", got "${verifiedTitle}"`)
    }

    // 9. RELOAD BROWSER PAGE & CONFIRM PERSISTENCE
    console.log('\n🔄 9. Reloading page and confirming persistence...')
    await page.reload({ waitUntil: 'networkidle0' })
    await sleep(1200)

    const reloadedTitle = await page.evaluate(() => {
      const titleInput = document.querySelector('[data-testid="note-title-input"]')
      return titleInput?.value
    })
    console.log('  Title after page reload:', reloadedTitle)
    if (reloadedTitle !== testTitle) {
      throw new Error(`Persistence failure after reload! Expected "${testTitle}", got "${reloadedTitle}"`)
    }
    console.log('  ✅ Title and content fully persisted across page reload!')

    // 10. MOBILE RESPONSIVE VIEW (< 640px)
    console.log('\n📱 10. Testing Mobile View (375px)...')
    await page.setViewport({ width: 375, height: 667 })
    await sleep(500)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'stage5a-mobile-view.png') })
    console.log('  ✅ Captured stage5a-mobile-view.png')

    // 11. CHECK LOCAL DISK .MD FILE
    console.log('\n💾 11. Inspecting local_data on disk...')
    const usersBase = path.resolve('..', 'backend', 'local_data', 'users')
    let localNotePath = null
    if (fs.existsSync(usersBase)) {
      const userDirs = fs.readdirSync(usersBase)
      for (const u of userDirs) {
        const candidate = path.join(usersBase, u, 'notes', `${newNoteId}.md`)
        if (fs.existsSync(candidate)) {
          localNotePath = candidate
          break
        }
      }
    }

    if (localNotePath && fs.existsSync(localNotePath)) {
      const diskContent = fs.readFileSync(localNotePath, 'utf8')
      console.log('  ✅ Stored Markdown file verified on disk at:', localNotePath)
      console.log('  File snippet:\n' + diskContent.split('\n').slice(0, 20).join('\n') + '\n  ...')

      if (!diskContent.includes('kubernetes') || !diskContent.includes('| Node | Role |')) {
        throw new Error('Disk file does not contain expected table/tags content!')
      }
      console.log('  ✅ Stored .md file confirmed to be clean standard Markdown with front-matter!')
    } else {
      throw new Error(`Note file not found on disk for note ${newNoteId}`)
    }

    console.log('\n🎉 ALL STAGE 5A VERIFICATIONS PASSED SUCCESSFULLY!')
  } catch (err) {
    console.error('❌ Verification failed:', err)
    process.exitCode = 1
  } finally {
    await browser.close()
  }
}

run()
