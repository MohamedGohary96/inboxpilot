# InboxPilot

An AI co-pilot for your Gmail and Slack — turns incoming messages into a clean, prioritized to-do list, drafts replies in your voice, books meetings from natural language, and digests GitHub notifications.

Runs entirely on your Mac, Linux box, or Windows PC. The only thing leaving your machine is the message subject + body sent to the LLM provider **you** choose (Groq, OpenAI, Anthropic, or a local Ollama-style endpoint).

---

## Features

- **AI inbox triage** — every email and Slack DM is classified as a task or noise by the LLM provider you pick. Pre-filter strips out newsletters, automated alerts, and calendar invites before they hit the LLM.
- **Bring your own model** — switch between Groq, OpenAI, Anthropic, or a local OpenAI-compatible endpoint (Ollama, vLLM, LM Studio) right from Settings. Each provider has its own curated model list with a free-form "Other (custom)…" option for anything not listed.
- **Smart deadlines** — extracts "by Friday EOD" / "tomorrow at 3pm" from message text and turns it into a reply-by datetime, with overdue / 1h / 24h reminders via native desktop notifications.
- **AI reply drafter** — write the reply in your voice from a one-line instruction ("decline politely", "ask for more time"), or hit Generate for a default professional reply. One-click **Open in Gmail** pre-fills the compose window.
- **Smart meeting booking** — type "Book a meeting tomorrow at 11 AM for 30 minutes" in the same reply-instructions box. The app finds a free slot on your Google Calendar, sends an invite to the sender (adding you as an attendee), then drafts a confirmation reply — all in one shot.
- **Calendar view** — week grid showing your existing Google Calendar events plus reply-by deadlines as todo blocks.
- **GitHub news tab** — separates PR / issue / release / security / discussion / newsletter mails by repo. Each item shows the event line ("@user approved this pull request"), an "Open in GitHub" deep link to the PR/Issue/Discussion, optional LLM one-line summary on demand, and a "task" badge when the same mail is also tracked as a to-do.
- **Priority senders (VIPs)** — flag specific emails as high-priority with custom reply windows (e.g., respond to the CEO within 2 hours).
- **Connection awareness** — colored dot on the account avatar (green = OK, amber pulsing = Gmail session expired). Banners prompt re-authentication when needed and call out a missing API key.
- **Editable Gmail query** — visual builder for the common filters (look-back, category excludes, unread-only) plus a textarea for any raw Gmail search operator (`from:`, `label:`, `has:attachment`, etc.).
- **Themes** — pick from several color palettes in Settings; applied via CSS variables instantly.
- **Slack DMs** — opt-in. Pulls Slack direct messages into the same task list, with the same AI reply / meeting features.

---

## Architecture

| Layer        | Stack |
|--------------|-------|
| Backend      | FastAPI + SQLite + APScheduler |
| Frontend     | Vue 3 + TypeScript + Tailwind + Pinia, served from the same FastAPI process |
| LLM          | Pluggable: Groq (default) · OpenAI · Anthropic · Local (Ollama / OpenAI-compatible) |
| Integrations | Gmail API, Google Calendar API, Google People API, Slack Web API |
| Credentials  | OS-native keyring (macOS Keychain · Windows Credential Locker · Linux Secret Service / KWallet) |
| Data         | per-OS user data dir via [`platformdirs`](https://pypi.org/project/platformdirs/) — never leaves your machine |
| Notifications| `pync` on macOS, `plyer` on Linux/Windows, with graceful fallbacks |

---

## Platform support

| Platform | Status | Notes |
|---|---|---|
| **macOS 12+**       | ✓ Primary    | Native notifications with click-to-open; tested daily by the author |
| **Linux**           | ✓ Supported  | Install `libnotify-bin` for toasts; no click handler on notifications |
| **Windows 10/11**   | ✓ Supported  | Use `start.ps1` instead of `start.sh`; toasts via `plyer`; no click handler |

---

## Prerequisites

- **Python 3.11+**
- **Node 20+**
- **Google Cloud project** with the Gmail, Calendar, People, and Contacts APIs enabled — you'll download an OAuth `client_secrets.json` from it
- **An LLM provider** — at least one of:
  - [Groq API key](https://console.groq.com/keys) (free tier, default)
  - [OpenAI API key](https://platform.openai.com/api-keys)
  - [Anthropic API key](https://console.anthropic.com)
  - A local OpenAI-compatible endpoint such as [Ollama](https://ollama.com) (no key needed)
- Optional: a **Slack User OAuth Token** (`xoxp-…`) to pull Slack DMs

---

## Setup

The 5-minute happy path:

### 1. Clone and launch

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

The launcher installs anything that's missing (frontend deps, frontend build, backend CLI), then starts the app and opens it in your browser. Safe to re-run — each step is skipped if already done. `start.sh dev` (or `.\start.ps1 dev`) runs Vite hot-reload at `localhost:5173` alongside the backend.

If `client_secrets.json` hasn't been placed yet, the script tells you exactly where to put it and opens that folder in your file manager.

### 2. Set up Google Cloud (one-time, ~5 minutes)

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. **Enable APIs**: Gmail API, Google Calendar API, People API, Contacts API.
3. **OAuth consent screen** → External, add your own Gmail as a test user.
4. **Credentials** → Create credentials → OAuth client ID → **Desktop app**.
5. Download the JSON, rename it to `client_secrets.json`, and put it at:
   - **macOS / Linux**: `~/inboxpilot/client_secrets.json`
   - **Windows**: `%USERPROFILE%\inboxpilot\client_secrets.json`

   The launcher creates this folder for you on first run. The expected file shape is in `client_secrets.example.json` at the root of this repo.

### 3. Connect Gmail

Open the app in your browser (the launcher does this for you at `http://127.0.0.1:8765`), click **Connect Gmail**, complete the OAuth flow. Credentials are cached in your OS keyring.

### 4. Pick an LLM provider

In **Settings** (gear icon) → **AI provider**:

1. **Provider** — pick Groq, OpenAI, Anthropic, or Local.
2. **Model** — pick from the curated list for that provider, or choose **Other (custom)…** to type any model ID the provider supports.
3. **API key** — paste your key (`gsk_…` for Groq, `sk-…` for OpenAI, `sk-ant-…` for Anthropic). Local needs no key — set the **Base URL** instead (e.g. `http://localhost:11434/v1` for Ollama).

Keys are stored in your OS keyring.

### 5. Set your display name

While you're in Settings, set **Display name** at the top — it's used in the sign-off of AI-drafted replies (e.g. `Best,\nMohamed`). Leave blank to derive it from your email.

Optional: connect **Slack** in the same Settings panel if you want DMs to show up in the task list.

That's it — the first poll starts within 5 minutes; click **Poll now** in the header to skip the wait.

### Manual setup (skip the launcher)

```bash
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot
pip install -e backend/
cd frontend && npm install && npm run build && cd ..
make build      # copies the build into the backend package
todo-mail start
```

---

## Running

```bash
./start.sh         # one-shot: install-if-needed → run → open browser
./start.sh dev     # backend + Vite hot-reload at :5173
# or, after first setup:
todo-mail start
```

After the first run, the app polls Gmail (and Slack, if connected) every 5 minutes by default. Configure that and everything else from **Settings**.

---

## Configuration

Everything you'll touch day-to-day lives in **Settings** (gear icon in the header):

| Section | What you can do |
|---|---|
| **Display name** | Sign-off used by AI replies. Blank = derive from email. |
| **Defaults** | Reply-by window (days + hour), poll interval, reminder offsets (e.g. `24,1,0`). |
| **Gmail filter** | Visual builder (look-back slider, category excludes, unread-only) + a textarea for the raw query that accepts any Gmail search operator. |
| **Priority senders (VIPs)** | Per-sender reply windows in hours; VIPs auto-classify as `priority=high`. |
| **AI provider** | Switch between Groq / OpenAI / Anthropic / Local; pick a model from the curated list or type a custom one; paste API keys or set the local base URL. |
| **Slack** | Paste a User OAuth Token + look-back days. |
| **Theme** | Pick a color palette; applies instantly. |
| **Re-authenticate / Sign out** | From the account menu in the header. |

### config.json (advanced, optional)

For tweaks not exposed in the UI, edit the per-OS config file:

- **macOS**: `~/Library/Application Support/inboxpilot/config.json`
- **Linux**: `~/.config/inboxpilot/config.json`
- **Windows**: `%APPDATA%\inboxpilot\config.json`

```json
{
  "model": "llama-3.3-70b-versatile",
  "prompt_version": "v3",
  "pre_filter": true,
  "llm_provider": "groq",
  "llm_base_url": ""
}
```

All keys are optional; missing keys fall back to the values in Settings → AI provider.

### Data location

The local SQLite DB lives at:

- **macOS**: `~/Library/Application Support/inboxpilot/todo.db`
- **Linux**: `~/.local/share/inboxpilot/todo.db`
- **Windows**: `%LOCALAPPDATA%\inboxpilot\todo.db`

On first run, any existing legacy DB at `~/.local/share/todo-mail/todo.db` is migrated automatically.

---

## Development

```bash
make dev-backend   # uvicorn with --reload on :8765
make dev-frontend  # vite on :5173 with API proxy
```

Or the unified shortcut:

```bash
./start.sh dev     # backend (no browser) + Vite at :5173, opens :5173
```

Backend tests:

```bash
cd backend && pytest
```

Linux Docker smoke test (verifies cross-platform imports, paths, and launcher):

```bash
docker build -t inboxpilot-smoke -f Dockerfile .
docker run --rm inboxpilot-smoke bash /app/run-smoke.sh
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Gmail session expired" amber banner | Click **Reconnect Gmail** in the account menu — happens when Google revokes the refresh token (every 7 days for unverified OAuth apps in testing). The avatar dot turns amber when this happens. |
| "API key not set" amber banner | Open **Settings → AI provider** and paste a key for the active provider. |
| Polling stops silently | Check the terminal where you ran `todo-mail start`. Most common cause is an expired LLM quota — generate a new key and paste it in **Settings → AI provider**. |
| Port 8765 already in use | macOS/Linux: `lsof -ti :8765 \| xargs kill -9`. Windows: `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8765).OwningProcess`. |
| Contact photos not showing | Make sure People API is enabled on your Google Cloud project, then hard-refresh the browser. |
| GitHub PR / Issue mails missing from News tab | The detector keys off `[owner/repo]` in the subject and `(PR #…) / (Issue #…)`. If your mails follow a different format, open an issue with a sample subject. |
| No desktop notifications on Linux | Install `libnotify-bin` (`sudo apt install libnotify-bin`) — `plyer` falls back to `notify-send`. |
| No notifications on Windows | Toast support relies on Windows 10+ Action Center. Make sure Focus Assist isn't blocking notifications. |
| Local LLM (Ollama) calls failing | Confirm Ollama is running (`ollama serve`), the base URL ends in `/v1`, and the model is pulled (`ollama pull llama3`). |

---

## License

[MIT](LICENSE) — do whatever you want with it.

---

_Built as a personal productivity experiment. Not affiliated with Google, Slack, Groq, OpenAI, Anthropic, or GitHub._
