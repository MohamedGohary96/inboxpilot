# InboxPilot

An AI co-pilot for your Gmail and Slack — turns incoming messages into a clean, prioritized to-do list, drafts replies in your voice, books meetings from natural language, and digests GitHub notifications.

Runs entirely on your machine. The only thing leaving your machine is the message subject + body sent to the LLM provider **you** choose (Groq, OpenAI, Anthropic, or a local Ollama-style endpoint).

---

## Download

Pre-built installers are attached to every [GitHub Release](https://github.com/MohamedGohary96/inboxpilot/releases/latest):

| Platform | File |
|----------|------|
| macOS (Apple Silicon) | `InboxPilot-mac-arm64.dmg` |
| macOS (Intel) | `InboxPilot-mac-x86_64.dmg` |
| Windows 10/11 | `InboxPilot-windows-x86_64.exe` |

**Mac:** open the `.dmg`, drag InboxPilot to Applications, double-click to launch.  
**Windows:** run the `.exe` directly — no installation needed.

On first launch the **onboarding wizard** walks you through everything:

1. **Upload your Google credentials file** — drag-and-drop `client_secrets.json` into the app (instructions for creating it are built into the wizard).
2. **Sign in with Google** — a browser window opens for OAuth; come back once you've approved access.
3. **Add an AI provider key** — paste a Groq, OpenAI, or Anthropic key in Settings → AI, or point it at a local Ollama endpoint.

No terminal required.

---

## Features

- **AI inbox triage** — every email and Slack DM is classified as a task or noise by the LLM provider you pick. Pre-filter strips out newsletters, automated alerts, and calendar invites before they hit the LLM.
- **Bring your own model** — switch between Groq, OpenAI, Anthropic, or a local OpenAI-compatible endpoint (Ollama, vLLM, LM Studio) right from Settings. Each provider has its own curated model list with a free-form "Other (custom)…" option for anything not listed.
- **Smart deadlines** — extracts "by Friday EOD" / "tomorrow at 3pm" from message text and turns it into a reply-by datetime, with overdue / 1h / 24h reminders via native desktop notifications.
- **AI reply drafter** — write the reply in your voice from a one-line instruction ("decline politely", "ask for more time"), or hit Generate for a default professional reply. One-click **Open in Gmail** pre-fills the compose window.
- **Smart meeting booking** — type "Book a meeting tomorrow at 11 AM for 30 minutes" in the same reply-instructions box. The app finds a free slot on your Google Calendar, sends an invite to the sender, then drafts a confirmation reply — all in one shot.
- **Calendar view** — week grid showing your existing Google Calendar events plus reply-by deadlines as todo blocks.
- **GitHub news tab** — separates PR / issue / release / security / discussion / newsletter mails by repo. Each item shows the event line, an "Open in GitHub" deep link, optional LLM one-line summary on demand, and a "task" badge when the same mail is also tracked as a to-do.
- **Priority senders (VIPs)** — flag specific senders as high-priority with custom reply windows (e.g., respond within 2 hours).
- **Connection awareness** — colored dot on the account avatar (green = OK, amber pulsing = Gmail session expired). Banners prompt re-authentication when needed.
- **Editable Gmail query** — visual builder for common filters (look-back, category excludes, unread-only) plus a textarea for any raw Gmail search operator.
- **Themes** — pick from several color palettes in Settings; applied via CSS variables instantly.
- **Slack DMs** — opt-in. Pulls Slack direct messages into the same task list, with the same AI reply / meeting features.

---

## Architecture

| Layer        | Stack |
|--------------|-------|
| Backend      | FastAPI + SQLite + APScheduler |
| Frontend     | Vue 3 + TypeScript + Tailwind, served from the same FastAPI process |
| LLM          | Pluggable: Groq (default) · OpenAI · Anthropic · Local (Ollama / OpenAI-compatible) |
| Integrations | Gmail API, Google Calendar API, Google People API, Slack Web API |
| Credentials  | OS-native keyring (macOS Keychain · Windows Credential Locker · Linux Secret Service) |
| Data         | per-OS user data dir via [`platformdirs`](https://pypi.org/project/platformdirs/) — never leaves your machine |
| Notifications| `pync` on macOS, `plyer` on Linux/Windows, with graceful fallbacks |
| Installer    | PyInstaller bundle → Mac `.app` / `.dmg` · Windows single `.exe` |
| CI/CD        | GitHub Actions — builds Mac (arm64 + x86_64) and Windows in parallel on every version tag |

---

## Platform support

| Platform | Status | Notes |
|---|---|---|
| **macOS 12+**       | ✓ Primary    | Native notifications with click-to-open; standalone `.dmg` available |
| **Linux**           | ✓ Supported  | Run from source; install `libnotify-bin` for toasts |
| **Windows 10/11**   | ✓ Supported  | Standalone `.exe` available; toasts via `plyer` |

---

## Run from source

If you prefer to run InboxPilot directly from the code:

### Prerequisites

- **Python 3.11+**
- **Node 20+**
- **Google Cloud project** with Gmail, Calendar, People, and Contacts APIs enabled
- **An LLM provider key** — Groq (free tier), OpenAI, Anthropic, or a local Ollama endpoint

### Quick start

**macOS / Linux:**
```bash
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot
./start.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot
.\start.ps1
```

The launcher installs anything that's missing, builds the frontend, starts the server, and opens the browser. Safe to re-run. `start.sh dev` runs Vite hot-reload at `localhost:5173`.

On first launch the **onboarding wizard** opens automatically and walks you through uploading your Google credentials and signing in.

### Manual setup

```bash
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot
pip install -e backend/
cd frontend && npm install && npm run build && cd ..
make build      # copies the frontend build into the backend package
todo-mail start
```

---

## Google Cloud setup (one-time, ~5 minutes)

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project named **InboxPilot**.
2. **Enable APIs**: Gmail API, Google Calendar API, People API, Contacts API.
3. **OAuth consent screen** → External → add your Gmail as a test user.
4. **Credentials** → Create credentials → OAuth client ID → **Desktop app**.
5. Download the JSON — the onboarding wizard lets you drag-and-drop it directly into the app.

If running from source, place the file at:
- **macOS / Linux**: `~/inboxpilot/client_secrets.json`
- **Windows**: `%USERPROFILE%\inboxpilot\client_secrets.json`

---

## Configuration

Everything you'll touch day-to-day lives in **Settings** (gear icon), organized into four tabs:

| Tab | What you can configure |
|-----|------------------------|
| **General** | Display name, reply-by window, poll interval, reminder offsets, theme |
| **AI** | Provider (Groq / OpenAI / Anthropic / Local), model, API key or base URL |
| **Gmail** | Visual query builder (look-back, category excludes, unread-only) + raw Gmail search textarea |
| **Integrations** | Slack User OAuth Token, look-back days, priority senders (VIPs) |

### Data location

The local SQLite DB lives at:

- **macOS**: `~/Library/Application Support/inboxpilot/todo.db`
- **Linux**: `~/.local/share/inboxpilot/todo.db`
- **Windows**: `%LOCALAPPDATA%\inboxpilot\todo.db`

API keys are stored in the OS keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service) under the service name **InboxPilot** — never written to disk.

---

## Development

```bash
make dev-backend   # uvicorn with --reload on :8765
make dev-frontend  # vite on :5173 with API proxy
./start.sh dev     # both at once, opens :5173
```

Backend tests:

```bash
cd backend && pytest
```

Linux Docker smoke test:

```bash
docker build -t inboxpilot-smoke -f Dockerfile .
docker run --rm inboxpilot-smoke bash /app/run-smoke.sh
```

### Building installers locally

```bash
make build                          # build frontend → backend/todo_mail/dist/
pyinstaller installer/InboxPilot.spec --distpath installer/dist -y
# Mac only:
create-dmg --volname "InboxPilot" ... installer/dist/InboxPilot.dmg installer/dist/InboxPilot.app
```

Releases are built automatically via GitHub Actions on every `v*` tag push — see [`.github/workflows/build-installers.yml`](.github/workflows/build-installers.yml).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Gmail session expired" amber banner | Click **Reconnect Gmail** in the account menu — happens when Google revokes the refresh token (every 7 days for unverified OAuth apps in testing). |
| "API key not set" amber banner | Open **Settings → AI** and paste a key for the active provider. |
| Polling stops silently | Check the terminal (or macOS Console for the `.app`). Most common cause is an expired LLM quota. |
| Port 8765 already in use | macOS/Linux: `lsof -ti :8765 \| xargs kill -9`. Windows: `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8765).OwningProcess`. |
| macOS Keychain prompt on launch | Enter your Mac login password and click **Always Allow** — the app reads its stored API keys from the keychain on startup. |
| Contact photos not showing | Make sure People API is enabled on your Google Cloud project, then hard-refresh. |
| Local LLM (Ollama) calls failing | Confirm Ollama is running (`ollama serve`), the base URL ends in `/v1`, and the model is pulled (`ollama pull llama3`). |
| No desktop notifications on Linux | Install `libnotify-bin` (`sudo apt install libnotify-bin`). |

---

## License

[MIT](LICENSE) — do whatever you want with it.

---

_Built as a personal productivity experiment. Not affiliated with Google, Slack, Groq, OpenAI, Anthropic, or GitHub._
