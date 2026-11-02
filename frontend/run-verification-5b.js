import { spawn } from 'child_process'
import http from 'http'

const PYTHON_PATH = 'd:\\cloud-note-taking-app\\backend\\.venv\\Scripts\\python.exe'
const BACKEND_DIR = 'd:\\cloud-note-taking-app\\backend'
const FRONTEND_DIR = 'd:\\cloud-note-taking-app\\frontend'

async function checkUrl(url, timeoutMs = 1500) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) })
    return res.status >= 200 && res.status < 400
  } catch (e) {
    console.log(`[checkUrl ${url} error]:`, e.message || e.code || e)
    return false
  }
}

async function waitForServer(url, name, maxRetries = 30) {
  console.log(`Waiting for ${name} at ${url}...`)
  for (let i = 0; i < maxRetries; i++) {
    const ok = await checkUrl(url)
    if (ok) {
      console.log(`✅ ${name} is ready!`)
      return true
    }
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error(`Timed out waiting for ${name} at ${url}`)
}

async function main() {
  console.log('🚀 Launching backend and frontend servers for verification...')

  // 1. Start backend
  const backendProc = spawn(PYTHON_PATH, ['wsgi.py'], {
    cwd: BACKEND_DIR,
    env: { ...process.env, PYTHONPATH: BACKEND_DIR },
    stdio: 'pipe',
  })
  backendProc.stdout.on('data', (d) => console.log('[Backend]', d.toString().trim()))
  backendProc.stderr.on('data', (d) => console.log('[Backend Err]', d.toString().trim()))

  // 2. Start frontend
  const frontendProc = spawn('cmd.exe', ['/c', 'npm', 'run', 'dev'], {
    cwd: FRONTEND_DIR,
    stdio: 'pipe',
  })
  frontendProc.stdout.on('data', (d) => console.log('[Frontend]', d.toString().trim()))
  frontendProc.stderr.on('data', (d) => console.log('[Frontend Err]', d.toString().trim()))

  try {
    await waitForServer('http://127.0.0.1:8000/api/health', 'Backend API')
    await waitForServer('http://localhost:5173', 'Frontend Dev Server')

    console.log('\n▶️ Executing verify-stage5b.js...')
    const verifyProc = spawn('node', ['verify-stage5b.js'], {
      cwd: FRONTEND_DIR,
      stdio: 'inherit',
    })

    const code = await new Promise((resolve) => {
      verifyProc.on('exit', resolve)
    })

    if (code !== 0) {
      console.error(`❌ Verification script failed with code ${code}`)
      process.exitCode = code || 1
    } else {
      console.log('✅ Verification script completed with code 0')
    }
  } finally {
    console.log('Shutting down server processes...')
    try {
      backendProc.kill()
    } catch {}
    try {
      frontendProc.kill()
    } catch {}
    spawn('taskkill', ['/F', '/T', '/PID', String(backendProc.pid)], { stdio: 'ignore' })
    spawn('taskkill', ['/F', '/T', '/PID', String(frontendProc.pid)], { stdio: 'ignore' })
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
