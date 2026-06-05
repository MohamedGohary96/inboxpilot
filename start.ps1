# One-shot launcher for InboxPilot on Windows.
#   .\start.ps1          → prod: backend serves the built frontend at :8765
#   .\start.ps1 dev      → dev:  backend :8765 + Vite hot-reload at :5173 (opens :5173)
# Installs anything that's missing. Safe to run multiple times.

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$Mode = if ($args.Count -ge 1) { $args[0] } else { 'prod' }

# ── Prereq checks ─────────────────────────────────────────────────────
function Require-Cmd($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Error "X $name not found. $hint"
    exit 1
  }
}

Require-Cmd 'python' 'Install Python 3.11+ from https://www.python.org/downloads/ and rerun.'
Require-Cmd 'npm'    'Install Node 20+ from https://nodejs.org and rerun.'

# pip ships with Python on Windows; surface a cleaner error if it's missing
if (-not (Get-Command 'pip' -ErrorAction SilentlyContinue)) {
  Write-Error 'X pip not found. Run: python -m ensurepip --upgrade'
  exit 1
}

# ── 1. Frontend deps ──────────────────────────────────────────────────
if (-not (Test-Path 'frontend\node_modules')) {
  Write-Host '→ Installing frontend dependencies (one-time, ~30s)…'
  Push-Location frontend
  npm install --silent
  Pop-Location
}

# ── 2. Frontend build (prod only) — rebuild if source newer than dist ─
function Needs-Build {
  $dist = 'backend\todo_mail\dist\index.html'
  if (-not (Test-Path $dist)) { return $true }
  $distTime = (Get-Item $dist).LastWriteTime
  $watched = @(
    'frontend\src',
    'frontend\index.html',
    'frontend\package.json',
    'frontend\tailwind.config.js',
    'frontend\vite.config.ts'
  ) | Where-Object { Test-Path $_ }
  $newest = Get-ChildItem -Path $watched -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($newest -and ($newest.LastWriteTime -gt $distTime)) { return $true }
  return $false
}

if ($Mode -ne 'dev' -and (Needs-Build)) {
  Write-Host '→ Building frontend…'
  Push-Location frontend
  npm run build --silent
  Pop-Location
  if (Test-Path 'backend\todo_mail\dist') {
    Remove-Item -Recurse -Force 'backend\todo_mail\dist'
  }
  Copy-Item -Recurse 'frontend\dist' 'backend\todo_mail\dist'
}

# ── 3. Backend install ────────────────────────────────────────────────
if (-not (Get-Command 'todo-mail' -ErrorAction SilentlyContinue)) {
  Write-Host '→ Installing backend (todo-mail CLI)…'
  pip install -e backend --quiet
}

# ── 4. Ensure visible config folder ───────────────────────────────────
$InboxDir = Join-Path $HOME 'inboxpilot'
if (-not (Test-Path $InboxDir)) {
  New-Item -ItemType Directory -Path $InboxDir | Out-Null
}

$secretsPaths = @(
  (Join-Path $InboxDir 'client_secrets.json'),
  (Join-Path $HOME '.config\todo-mail\client_secrets.json'),
  (Join-Path (Get-Location) 'client_secrets.json')
)
$hasSecrets = $secretsPaths | Where-Object { Test-Path $_ }

if (-not $hasSecrets) {
  Write-Host @"

[!] No client_secrets.json found.

   1. Go to https://console.cloud.google.com/
   2. Create a project, enable Gmail / Calendar / People / Contacts APIs
   3. Credentials → OAuth client ID → Desktop app → download JSON
   4. Rename it to client_secrets.json and drop it in:

         $InboxDir

   Then run .\start.ps1 again.

"@
  Start-Process explorer.exe $InboxDir
  exit 1
}

# ── 5. Launch ─────────────────────────────────────────────────────────
if ($Mode -eq 'dev') {
  Write-Host '→ Starting backend (no-browser) at http://127.0.0.1:8765 …'
  $backend = Start-Process -PassThru -NoNewWindow -FilePath 'todo-mail' -ArgumentList 'start','--no-browser'

  Write-Host '→ Starting Vite dev server at http://localhost:5173 …'
  $vite = Start-Process -PassThru -NoNewWindow -FilePath 'npm' -ArgumentList 'run','dev','--silent' -WorkingDirectory 'frontend'

  $cleanup = {
    Write-Host "`n→ Stopping…"
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
    if ($vite -and -not $vite.HasExited) { Stop-Process -Id $vite.Id -Force }
  }
  try {
    # Wait for Vite to be reachable, then open the browser
    for ($i = 0; $i -lt 30; $i++) {
      try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:5173/' -TimeoutSec 1
        if ($r.StatusCode -eq 200) { break }
      } catch { Start-Sleep -Milliseconds 500 }
    }
    Start-Process 'http://localhost:5173/'
    Write-Host "`nInboxPilot is running. Press Ctrl+C to stop."
    Wait-Process -Id $backend.Id, $vite.Id
  }
  finally {
    & $cleanup
  }
}
else {
  Write-Host '→ Starting InboxPilot at http://127.0.0.1:8765 …'
  & todo-mail start
}
