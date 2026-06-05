#!/usr/bin/env bash
# One-shot launcher for InboxPilot.
#   ./start.sh          → prod: backend serves the built frontend at :8765
#   ./start.sh dev      → dev:  backend :8765 + Vite hot-reload at :5173 (opens :5173)
# Installs anything that's missing. Safe to run multiple times.

set -e

cd "$(dirname "$0")"

MODE="${1:-prod}"

# Cross-platform "open this file/URL with the default handler".
# Mac uses `open`, Linux uses `xdg-open`. Silently no-ops elsewhere.
xopen() {
  if command -v open >/dev/null 2>&1; then
    open "$@" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$@" 2>/dev/null || true
  fi
}

# ── Prereq checks ─────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ Python 3 not found. Install it from https://www.python.org/downloads/ and rerun." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "✗ Node / npm not found. Install Node 20+ from https://nodejs.org and rerun." >&2
  exit 1
fi

PIP="$(command -v pip3 || command -v pip)"
if [ -z "$PIP" ]; then
  echo "✗ pip not found. Reinstall Python or run: python3 -m ensurepip --upgrade" >&2
  exit 1
fi

# ── 1. Frontend deps ──────────────────────────────────────────────────
if [ ! -d frontend/node_modules ]; then
  echo "→ Installing frontend dependencies (one-time, ~30s)…"
  (cd frontend && npm install --silent)
fi

# ── 2. Frontend build (prod only — dev mode uses Vite directly) ──────
needs_build() {
  [ ! -f backend/todo_mail/dist/index.html ] && return 0
  # Rebuild if any source file is newer than the bundled dist
  if find frontend/src frontend/index.html frontend/package.json frontend/tailwind.config.js frontend/vite.config.ts \
       -type f -newer backend/todo_mail/dist/index.html 2>/dev/null | grep -q .; then
    return 0
  fi
  return 1
}

if [ "$MODE" != "dev" ] && needs_build; then
  echo "→ Building frontend (source newer than current bundle)…"
  (cd frontend && npm run build --silent)
  rm -rf backend/todo_mail/dist
  cp -r frontend/dist backend/todo_mail/dist
fi

# ── 3. Backend install ────────────────────────────────────────────────
if ! command -v todo-mail >/dev/null 2>&1; then
  echo "→ Installing backend (todo-mail CLI)…"
  "$PIP" install -e backend/ --quiet
fi

# ── 4. Ensure visible config folder ───────────────────────────────────
mkdir -p "$HOME/inboxpilot"

if [ ! -f "$HOME/inboxpilot/client_secrets.json" ] \
   && [ ! -f "$HOME/.config/todo-mail/client_secrets.json" ] \
   && [ ! -f "./client_secrets.json" ]; then
  cat <<EOF

⚠  No client_secrets.json found.

   1. Go to https://console.cloud.google.com/
   2. Create a project, enable Gmail / Calendar / People / Contacts APIs
   3. Credentials → OAuth client ID → Desktop app → download JSON
   4. Rename it to client_secrets.json and drop it in:

         $HOME/inboxpilot/

   Then run ./start.sh again.

EOF
  xopen "$HOME/inboxpilot"
  exit 1
fi

# ── 5. Launch ─────────────────────────────────────────────────────────
if [ "$MODE" = "dev" ]; then
  echo "→ Starting backend (no-browser) at http://127.0.0.1:8765 …"
  todo-mail start --no-browser &
  BACKEND_PID=$!

  echo "→ Starting Vite dev server at http://localhost:5173 …"
  (cd frontend && npm run dev --silent) &
  VITE_PID=$!

  cleanup() {
    echo
    echo "→ Stopping…"
    kill "$BACKEND_PID" "$VITE_PID" 2>/dev/null || true
    wait 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  # Wait for Vite to be ready, then open the browser
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/ | grep -q '^200$'; then
      break
    fi
    sleep 0.5
  done
  xopen http://localhost:5173/

  echo
  echo "InboxPilot is running. Press Ctrl+C to stop."
  wait
else
  echo "→ Starting InboxPilot at http://127.0.0.1:8765 …"
  exec todo-mail start
fi
