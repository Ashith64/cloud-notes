$ErrorActionPreference = "Stop"

# Clean up any lingering processes from previous runs
Get-Process -Name node, python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | ForEach-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmd -like "*vite*" -or $cmd -like "*wsgi.py*") {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}
Start-Sleep -Seconds 1

Write-Host "Starting Backend..."
$backendProc = Start-Process -FilePath "d:\cloud-note-taking-app\backend\.venv\Scripts\python.exe" -ArgumentList "wsgi.py" -WorkingDirectory "d:\cloud-note-taking-app\backend" -NoNewWindow -PassThru

Write-Host "Starting Frontend..."
$env:TEMP="D:\temp"
$env:TMP="D:\temp"
$env:npm_config_cache="D:\npm-cache"
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory "d:\cloud-note-taking-app\frontend" -NoNewWindow -PassThru

# Wait for backend health
Write-Host "Waiting for backend on port 8000..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = curl.exe -s http://127.0.0.1:8000/api/health
        if ($res -like "*ok*") { $ready = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 600
}
if (!$ready) {
    Write-Host "Backend failed to start!"
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "Backend is ready!"

# Wait for frontend
Write-Host "Waiting for frontend on port 5173..."
$feReady = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = curl.exe -s http://localhost:5173/
        if ($res -like "*<!doctype html>*" -or $res -like "*<html*") { $feReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 600
}
if (!$feReady) {
    Write-Host "Frontend failed to start!"
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}
Write-Host "Frontend is ready!"

$testExit = 0
try {
    Write-Host "Running verify-stage5a.js with Edge..."
    Set-Location "d:\cloud-note-taking-app\frontend"
    node verify-stage5a.js
    $testExit = $LASTEXITCODE
} finally {
    Write-Host "Stopping servers..."
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
    Get-Process -Name node, python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | ForEach-Object {
        # Check if process is running vite or wsgi
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            if ($cmd -like "*vite*" -or $cmd -like "*wsgi.py*") {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
}

exit $testExit
