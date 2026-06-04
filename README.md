# InboxPilot

An AI co-pilot for your Gmail and Slack — turns incoming messages into a clean, prioritized to-do list, drafts replies in your voice, books meetings from natural language, and digests GitHub notifications.

Runs entirely on your Mac. The only thing leaving your machine is the message subject + body sent to the Groq API for classification and reply drafting.

---

## Features

- **AI inbox triage** — every email and Slack DM is classified as a task or noise by Groq (Llama 3.3). Pre-filter strips out newsletters and automated alerts before they hit the LLM.
- **Smart deadlines** — extracts "by Friday EOD" / "tomorrow at 3pm" from message text and turns it into a reply-by datetime, with overdue / 1h / 24h reminders via macOS notifications.
- **AI reply drafter** — write the reply in your voice from a one-line instruction ("decline politely", "ask for more time"), or just hit Generate for a default professional reply. One-click **Open in Gmail** pre-fills the compose window.
- **Smart meeting booking** — type "Book a meeting tomorrow at 11 AM for 30 minutes" in the same reply-instructions box. The app finds a free slot on your Google Calendar, sends an invite to the sender (and adds you as an attendee), then drafts a confirmation reply — all in one shot.
- **Calendar view** — week grid showing your existing Google Calendar events plus the reply-by deadlines as todo blocks.
- **GitHub news tab** — separates PR / issue / release / security / discussion / newsletter mails by repo. Each item shows the event line ("@user approved this pull request"), an "Open in GitHub" deep link to the PR/Issue/Discussion, optional LLM one-line summary on demand, and a "task" badge when the same mail is also tracked as a to-do.
- **Connection awareness** — colored dot on the account avatar (green = OK, amber = Gmail session expired). Banners prompt re-authentication when needed and call out a missing Groq API key.
- **Priority senders (VIPs)** — flag specific emails as high-priority with custom reply windows (e.g., respond to the CEO within 2 hours).
- **Slack DMs** — opt-in. Pulls Slack direct messages into the same task list, with smart classification and the same AI reply / meeting features.

---

## Architecture

| Layer        | Stack |
|--------------|-------|
| Backend      | FastAPI + SQLite + APScheduler |
| Frontend     | Vue 3 + TypeScript + Tailwind, served from the same FastAPI process |
| LLM          | Groq (`llama-3.3-70b-versatile` by default) |
| Integrations | Gmail API, Google Calendar API, Google People API, Slack Web API |
| Credentials  | macOS Keychain (via `keyring`) |
| Data         | `~/.local/share/todo-mail/todo.db` — never leaves your machine |

---

## Prerequisites

- **macOS** (the desktop notifications use `pync`; everything else is cross-platform)
- **Python 3.11+**
- **Node 20+**
- **Google Cloud project** with the Gmail API, Calendar API, and People API enabled — you'll download an OAuth `client_secrets.json` from it
- **Groq API key** — get one free at [console.groq.com](https://console.groq.com)
- Optional: a **Slack User OAuth Token** (`xoxp-…`) if you want to pull Slack DMs

---

## Setup

### Quick start (recommended)

```bash
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot
./start.sh
```

`start.sh` installs anything that's missing (frontend deps, frontend build, backend CLI), then starts the app and opens it in your browser. It's safe to re-run — each step is skipped if already done.

If `client_secrets.json` hasn't been placed yet, the script tells you exactly where to put it and opens that folder in Finder.

### Manual setup (if you'd rather do it yourself)

```bash
# 1. Clone the repo
git clone https://github.com/MohamedGohary96/inboxpilot.git
cd inboxpilot

# 2. Install the backend
pip install -e backend/

# 3. Build the frontend (this is what gets served at /)
cd frontend && npm install && npm run build
cd ..
make build      # copies the build into the backend package
```

### Google OAuth setup

1. Open the [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. **Enable APIs**: Gmail API, Google Calendar API, People API, Contacts API.
3. **OAuth consent screen** → External, add your own Gmail as a test user.
4. **Credentials** → Create credentials → OAuth client ID → **Desktop app**.
5. Download the JSON, rename it to `client_secrets.json`, and put it at:
   ```
   ~/inboxpilot/client_secrets.json
   ```
   This folder is visible in your home directory (no hidden-folder hunt). The example file shape is in `client_secrets.example.json` at the root of this repo.


### Groq API key

Easiest: start the app (next section), open **Settings** (gear icon) → **Groq API key** → Set key. Stored in the macOS Keychain.

Or, from the terminal:

```bash
todo-mail set-api-key
# paste your key from console.groq.com when prompted
```

### Slack (optional)

In the running app, open **Settings → Slack** and paste your User OAuth Token. See the in-app instructions for how to create a Slack app with `channels:history`, `groups:history`, `im:history`, `mpim:history`, `users:read`, and `users:read.email` scopes.

---

## Running

```bash
./start.sh         # one-shot: install-if-needed → run → open browser
# or, after first setup:
todo-mail start
```

This opens `http://127.0.0.1:8765` in your browser. Click **Connect Gmail** to complete the OAuth flow once — credentials are cached in the macOS Keychain. After that, the app polls Gmail every 5 minutes (configurable) and classifies new messages.

On first run, open **Settings** (gear icon) to:
- Paste your **Groq API key**
- Set your **Display name** (used in AI-drafted reply sign-offs — leave blank to derive from your email)

---

## Configuration

Everything you'll touch day-to-day lives in **Settings** (gear icon in the header):

- **Display name** — used in AI-drafted reply sign-offs. Leave blank to derive from your email.
- **Groq API key** — set / rotate from the UI, stored in the macOS Keychain.
- **Poll interval** (default 5 min) — how often Gmail and Slack are checked.
- **Reply-by defaults** — fallback window (days + hour) when the LLM finds no explicit deadline.
- **Reminder offsets** — when desktop notifications fire (default 24h, 1h, 0h before deadline).
- **Gmail query filter** — point-and-click builder for `is:unread`, category excludes, look-back window.
- **Slack token** + **look-back days** — opt-in pull of Slack DMs.
- **Priority senders (VIPs)** — per-sender reply windows (e.g., respond to the CEO within 2 hours).
- **Re-authenticate / Sign out of Gmail** — straight from the account menu.

For advanced tweaks, edit `~/.config/todo-mail/config.json` (optional, defaults shown):

```json
{
  "model": "llama-3.3-70b-versatile",
  "prompt_version": "v3",
  "pre_filter": true
}
```

---

## Development

```bash
make dev-backend   # uvicorn with --reload on :8765
make dev-frontend  # vite on :5173 with API proxy
```

Backend tests:

```bash
cd backend && pytest
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Gmail session expired" amber banner | Click **Reconnect Gmail** in the account menu — happens when Google revokes the refresh token (every 7 days for unverified OAuth apps in testing). The avatar dot turns amber when this happens. |
| "Groq API key not set" amber banner | Open **Settings → Groq API key → Set key**. Get a free key at [console.groq.com/keys](https://console.groq.com/keys). |
| Polling stops silently | Check the terminal where you ran `todo-mail start`. Most common cause is an expired Groq quota — generate a new key and paste it in **Settings → Groq API key**. |
| Port 8765 already in use | `lsof -ti :8765 \| xargs kill -9` |
| Contact photos not showing | Make sure People API is enabled on your Google Cloud project, then hard-refresh the browser. |
| GitHub PR / Issue mails missing from News tab | The detector keys off `[owner/repo]` in the subject and `(PR #…) / (Issue #…)`. If your mails follow a different format, open an issue with a sample subject. |

---

## License

[MIT](LICENSE) — do whatever you want with it.

---

_Built as a personal productivity experiment. Not affiliated with Google, Slack, Groq, or GitHub._
