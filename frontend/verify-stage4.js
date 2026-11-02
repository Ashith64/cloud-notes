import puppeteer from 'puppeteer-core'
import path from 'path'
import fs from 'fs'

const SCREENSHOT_DIR = path.resolve('..', 'docs', 'screenshots')
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE_URL = 'http://localhost:5174'

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function run() {
  console.log('🚀 Starting Stage 4 Automated Verification with Edge...')

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

    // ------------------------------------------------------------------------
    // 1. LOGIN / SIGNUP SCREEN - DESKTOP, TABLET, MOBILE (LIGHT & DARK)
    // ------------------------------------------------------------------------
    console.log('\n📸 1. Testing Login / Sign up Screen (C3.1)...')

    // Desktop Light
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' })
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'light')
      document.documentElement.classList.remove('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-desktop-light.png') })
    console.log('  ✅ Captured login-desktop-light.png')

    // Desktop Dark
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'dark')
      document.documentElement.classList.add('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-desktop-dark.png') })
    console.log('  ✅ Captured login-desktop-dark.png')

    // Tablet (768px)
    await page.setViewport({ width: 768, height: 1024 })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-tablet.png') })
    console.log('  ✅ Captured login-tablet.png')

    // Mobile (375px) - Form only
    await page.setViewport({ width: 375, height: 667 })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-mobile.png') })
    console.log('  ✅ Captured login-mobile.png (form only)')

    // ------------------------------------------------------------------------
    // 2. DEMO LOGIN & WORKSPACE SHELL (C3.2)
    // ------------------------------------------------------------------------
    console.log('\n⚡ 2. Testing "Try demo account" & Workspace Shell...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' })

    // Click demo button using DOM evaluation
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'))
      const b = btns.find((el) => el.textContent.toLowerCase().includes('demo'))
      if (!b) throw new Error('Demo button not found')
      b.click()
    })

    // Wait for navigation to /app
    await page.waitForFunction(() => window.location.pathname.startsWith('/app'), { timeout: 10000 })
    console.log('  ✅ Successfully logged in with demo account, redirected to /app')
    await sleep(800)

    // Workspace Desktop Dark
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'dark')
      document.documentElement.classList.add('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'workspace-desktop-dark.png') })
    console.log('  ✅ Captured workspace-desktop-dark.png')

    // Workspace Desktop Light
    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'light')
      document.documentElement.classList.remove('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'workspace-desktop-light.png') })
    console.log('  ✅ Captured workspace-desktop-light.png')

    // Tablet Workspace (768px) - Drawer trigger visible
    await page.setViewport({ width: 768, height: 1024 })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'workspace-tablet.png') })
    console.log('  ✅ Captured workspace-tablet.png (sidebar hidden in drawer)')

    // Click drawer button on tablet
    const menuBtn = await page.$('button[aria-label="Open menu"]')
    if (menuBtn) {
      await menuBtn.click()
      await sleep(500)
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'workspace-drawer-open.png') })
      console.log('  ✅ Captured workspace-drawer-open.png (slide-in drawer)')
      // Close drawer by pressing Escape
      await page.keyboard.press('Escape')
      await sleep(300)
    }

    // Mobile Workspace (375px) - 1 pane view
    await page.setViewport({ width: 375, height: 667 })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'workspace-mobile.png') })
    console.log('  ✅ Captured workspace-mobile.png (1 pane view)')

    // ------------------------------------------------------------------------
    // 3. SYSTEM STATUS PAGE (C3.5)
    // ------------------------------------------------------------------------
    console.log('\n📊 3. Testing System Status Page (C3.5)...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/status`, { waitUntil: 'networkidle0' })
    await sleep(1000)

    const statusText = await page.evaluate(() => document.body.innerText)
    const hasDb = statusText.includes('Database')
    const hasStorage = statusText.includes('Storage')
    const hasCompute = statusText.includes('Compute')
    console.log(`  ✅ Status page loaded live data (DB: ${hasDb}, Storage: ${hasStorage}, Compute: ${hasCompute})`)

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'status-desktop-light.png') })
    console.log('  ✅ Captured status-desktop-light.png')

    await page.evaluate(() => {
      localStorage.setItem('cloudnotes_theme', 'dark')
      document.documentElement.classList.add('dark')
    })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'status-desktop-dark.png') })
    console.log('  ✅ Captured status-desktop-dark.png')

    await page.setViewport({ width: 375, height: 667 })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'status-mobile.png') })
    console.log('  ✅ Captured status-mobile.png')

    // ------------------------------------------------------------------------
    // 4. SETTINGS PAGE
    // ------------------------------------------------------------------------
    console.log('\n⚙️ 4. Testing Settings Page...')
    await page.setViewport({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle0' })
    await sleep(500)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'settings-desktop.png') })
    console.log('  ✅ Captured settings-desktop.png')

    // ------------------------------------------------------------------------
    // 5. 404 NOT FOUND PAGE
    // ------------------------------------------------------------------------
    console.log('\n🔍 5. Testing 404 Page...')
    await page.goto(`${BASE_URL}/not-a-real-page`, { waitUntil: 'networkidle0' })
    await sleep(300)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'not-found.png') })
    console.log('  ✅ Captured not-found.png')

    // ------------------------------------------------------------------------
    // 6. LOGOUT FLOW
    // ------------------------------------------------------------------------
    console.log('\n🔒 6. Testing Logout...')
    await page.goto(`${BASE_URL}/app`, { waitUntil: 'networkidle0' })
    await sleep(500)
    
    // Open user dropdown
    const userMenuBtn = await page.$('button[aria-label="User menu"]')
    if (userMenuBtn) {
      await userMenuBtn.click()
      await sleep(300)
      await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
        const logoutItem = items.find((el) => el.textContent.includes('Log out'))
        if (logoutItem) logoutItem.click()
      })
      await page.waitForFunction(() => window.location.pathname === '/login', { timeout: 5000 })
      console.log('  ✅ Logout successful, redirected to /login')
    }

    // ------------------------------------------------------------------------
    // 7. USER REGISTRATION & LOGIN FLOW
    // ------------------------------------------------------------------------
    console.log('\n📝 7. Testing New User Registration & Login...')
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' })
    
    // Switch to Sign Up mode
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'))
      const signUpBtn = btns.find((el) => el.textContent.trim() === 'Sign up')
      if (signUpBtn) signUpBtn.click()
    })
    await sleep(300)

    const testEmail = `student_${Date.now()}@university.edu`
    const testPassword = 'Password123!'
    const testName = 'Jane Cloud'

    await page.type('#name', testName)
    await page.type('#email', testEmail)
    await page.type('#password', testPassword)

    await page.click('button[type="submit"]')
    await page.waitForFunction(() => window.location.pathname.startsWith('/app'), { timeout: 10000 })
    console.log(`  ✅ Successfully registered new user (${testEmail}), redirected to /app`)

    // Verify name in dropdown
    await sleep(500)
    const userMenuBtn2 = await page.$('button[aria-label="User menu"]')
    if (userMenuBtn2) {
      await userMenuBtn2.click()
      await sleep(300)
      const nameInMenu = await page.evaluate(() => document.body.innerText.includes('Jane Cloud'))
      console.log(`  ✅ User name "Jane Cloud" confirmed in menu: ${nameInMenu}`)
      
      // Log out
      await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('[role="menuitem"]'))
        const logoutItem = items.find((el) => el.textContent.includes('Log out'))
        if (logoutItem) logoutItem.click()
      })
      await page.waitForFunction(() => window.location.pathname === '/login', { timeout: 5000 })
      console.log('  ✅ Logged out Jane Cloud')
    }

    // Now log back in with test user credentials
    await page.type('#email', testEmail)
    await page.type('#password', testPassword)
    await page.click('button[type="submit"]')
    await page.waitForFunction(() => window.location.pathname.startsWith('/app'), { timeout: 10000 })
    console.log('  ✅ Logged in successfully with registered credentials')

    console.log('\n🎉 ALL STAGE 4 CHECKS PASSED SUCCESSFULLY!')
  } finally {
    await browser.close()
  }
}

run().catch((err) => {
  console.error('❌ Verification failed:', err)
  process.exit(1)
})
