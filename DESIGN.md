# Email-to-Todo Assistant — v1 Design Doc

## Goal
A local macOS tool that connects to a Gmail inbox, uses Claude to identify emails that require action from the user, lets the user assign a reply-by deadline, and surfaces reminders via desktop notifications and Google Calendar events.

## Scope

### In scope (v1)
- Gmail Inbox, read-only, single account
- Claude-based task detection and deadline extraction
- Local web UI (Vue 3 SPA) for reviewing, editing reply-by dates, marking replied/dismissed
- Desktop notifications at `reply_by - 24h`, `reply_by - 1h`, and overdue
- Google Calendar event per task (dedicated "Replies" calendar)
- SQLite persistence
- Secrets in macOS Keychain
- Evaluation CLI for measuring detection quality

### Out of scope (v1)
- Sending replies from the app
- Non-Inbox folders / labels
- Email-channel reminders (desktop + calendar only)
- Multi-account
- Windows / Linux packaging (code portable, but notifications + packaging are Mac-only)

## Answers locked in
| Question | Answer |
|---|---|
| Mail provider | Gmail |
| IT approval for third-party OAuth | Yes |
| OS | macOS |
| LLM provider | Groq (llama-3.3-70b-versatile) — free tier |
| Mail volume | ~30 emails/day |
| Folders | Inbox only |
| Calendar integration | Yes (Google Calendar) |
| Email-channel reminders | Dropped; desktop + calendar only |
| Expected LLM cost | ~$0/month (Groq free tier) |

---

## Stack (locked)

### Backend
- **Python 3.11+**
- **FastAPI** — JSON API only
- **SQLite** via stdlib `sqlite3`
- **`google-auth-oauthlib`** + **`google-api-python-client`** — Gmail + Calendar
- **`groq`** SDK — llama-3.3-70b-versatile (free tier)
- **APScheduler** — polling and reminder jobs
- **`keyring`** — macOS Keychain
- **`pync`** — macOS notifications (with `osascript` fallback)

### Frontend
- **Vue 3** — Composition API, `<script setup>`, **TypeScript**
- **Vite** — build tool and dev server
- **Tailwind CSS** — full PostCSS build (not CDN)
- **`@vuepic/vue-datepicker`** — date/time picker
- **`@heroicons/vue`** — icons
- **Native `fetch`** via a thin `api.ts` wrapper (no axios)
- **No Vue Router** (single view), **no Pinia** (component-local refs + a simple `useTasks` composable are enough for v1)

### Dev workflow
- `uvicorn` serves the API on `127.0.0.1:8765`
- `vite` dev server on `127.0.0.1:5173`, proxies `/api/*` → FastAPI
- Production: `npm run build` → `frontend/dist/`; FastAPI mounts `dist/` as static and serves `index.html` at `/`

### Packaging
- `pipx install todo-mail`
- Built frontend assets ship inside the Python wheel (`MANIFEST.in` includes `frontend/dist/**`)
- `todo-mail start` → starts FastAPI, opens `http://127.0.0.1:8765/` in default browser
- `todo-mail reauth`, `todo-mail label`, `todo-mail eval` as sibling CLI commands

---

## Repo layout
```
todo-mail/
  backend/
    todo_mail/
      __init__.py
      app.py           # FastAPI app + static mount
      api/             # routers: tasks, poll, feedback, settings
      db.py            # schema + connection
      mail.py          # Gmail client
      calendar.py      # Google Calendar client
      classify.py      # Claude prompt + client
      scheduler.py     # APScheduler jobs
      notify.py        # macOS notifications
      settings.py
      cli.py           # todo-mail entrypoints
    pyproject.toml
  frontend/
    src/
      main.ts
      App.vue
      components/
        TaskTable.vue
        TaskRow.vue
        FilterChips.vue
        
        ReplyByEditor.vue
      composables/
        useTasks.ts
      api.ts
      types.ts
    index.html
    vite.config.ts
    tailwind.config.js
    package.json
  Makefile
  DESIGN.md
```

---

## Auth flow
1. First run: CLI starts a one-shot loopback OAuth server, opens the browser to Google's consent screen.
2. Scopes requested:
   - `https://www.googleapis.com/auth/gmail.readonly` — read Inbox only
   - `https://www.googleapis.com/auth/calendar.events` — only events this app owns
3. Refresh token stored in macOS Keychain under `todo-mail:google-oauth`. Access token cached in memory.
4. Anthropic API key: read from `ANTHROPIC_API_KEY` env var on first run, then moved into Keychain (`todo-mail:anthropic-api-key`); env var no longer required.
5. Re-auth path: `todo-mail reauth` clears the Keychain entry and re-runs consent.

---

## Data model

```sql
messages
  id INTEGER PK
  gmail_message_id TEXT UNIQUE
  thread_id TEXT
  sender TEXT
  sender_email TEXT
  subject TEXT
  received_at DATETIME
  snippet TEXT
  body_text TEXT              -- plain text, stripped of quoted replies
  processed_at DATETIME

classifications               -- one row per LLM call (supports re-runs + eval)
  id INTEGER PK
  message_id FK
  model TEXT                  -- e.g. 'claude-sonnet-4-6'
  prompt_version TEXT         -- e.g. 'v1'
  is_task BOOLEAN
  raw_json TEXT               -- full LLM output
  created_at DATETIME

tasks                         -- created when is_task = true
  id INTEGER PK
  message_id FK UNIQUE
  summary TEXT
  asker TEXT
  extracted_deadline DATETIME NULL
  priority TEXT               -- 'low' | 'normal' | 'high'
  reply_by DATETIME
  status TEXT                 -- 'open' | 'replied' | 'dismissed' | 'snoozed'
  calendar_event_id TEXT NULL
  created_at DATETIME
  updated_at DATETIME

feedback                      -- user corrections, feed the eval set
  id INTEGER PK
  message_id FK
  kind TEXT                   -- 'not_a_task' | 'wrong_summary' | 'wrong_deadline' | 'missed_task'
  note TEXT NULL
  created_at DATETIME

settings
  key TEXT PK, value TEXT
```

---

## Task definition (v1)
An email **is a task for me** if any of:
- It asks a direct question I'm expected to answer
- It requests an action, decision, review, approval, or attendance from me specifically (not a mailing list at large)
- It's a meeting invite where I'm a required attendee and I haven't responded
- It's a reply in a thread where the last message leaves the ball in my court

An email **is not a task** if:
- It's a newsletter, marketing, notification, or automated alert
- It's an FYI / CC where no action is requested of me
- I'm one of many recipients and no action is attributed to me individually
- It's a reply confirming/acknowledging something I already did

Edge cases will be logged and the definition revisited after the first eval run.

---

## Polling loop
- Every **5 min**, query Gmail for `in:inbox is:unread -category:promotions -category:social newer_than:7d`, minus message IDs already in `messages`.
- Batched fetches, max 5 concurrent. For each new message: strip quoted history (regex + `html2text`), store, classify, maybe create task, maybe create calendar event.
- Idempotent on `gmail_message_id` unique constraint.

---

## Detection prompt (v1)
One Claude call per email; structured output via tool use.

```
System: You classify work emails as actionable tasks for the recipient.
Definition of 'task' (as above). Be conservative on the negative side:
if in doubt whether it's a task, mark is_task=true — the user can dismiss.

Tool: record_classification(
  is_task: bool,
  reasoning: str,                # 1 sentence
  task_summary: str | null,      # one-line imperative, e.g. "Review Q2 forecast deck"
  asker: str | null,             # person's name if identifiable
  extracted_deadline: str | null,# ISO-8601 if explicit or clearly implied; else null
  deadline_confidence: 'explicit' | 'implied' | 'none',
  priority: 'low' | 'normal' | 'high',
  priority_signals: list[str]    # e.g. ["urgent in subject", "CEO sender"]
)

User:
From: {sender_name} <{sender_email}>
To: {to}
Cc: {cc}
Subject: {subject}
Date: {received_at}
---
{body_text (truncated to 8k chars)}
```

**Default reply-by** when no deadline extracted: 2 business days from `received_at`, at 17:00 local. Configurable via `settings`.

---

## Calendar integration
- On task creation, create a Google Calendar event on a dedicated **"Replies"** calendar (auto-created on first run so it can be toggled off independently):
  - Start = `reply_by - 1h`, duration 15 min
  - Title: `Reply: {subject}`
  - Description: task summary + deep link to Gmail (`https://mail.google.com/mail/u/0/#inbox/{thread_id}`)
  - Store `event.id` on `tasks.calendar_event_id`
- On `reply_by` edit → PATCH event. On dismiss/replied → delete event.
- All events tagged with extended property `source=todo-mail`; we never touch events we don't own.

---

## Reminders
- APScheduler jobs per task at `reply_by - 24h`, `reply_by - 1h`, and `reply_by + 0` (overdue).
- Fire macOS notification via `pync`; clicking opens the task in the local UI.
- Jobs re-hydrated from DB on app start.

---

## UI (Vue 3 SPA, single view)

### Layout
- Header: last-poll timestamp, **Poll now** button, settings link
- Filter chips: **Open** · **Replied** · **Dismissed** · **All**
- Task table (sortable): sender · subject · task summary · reply-by (inline editable) · priority badge · status · row actions

### Row actions
- **Open in Gmail** — deep link
- **Mark replied**
- **Dismiss**
- **Not a task** — logs feedback
- **Wrong deadline** — logs feedback

### Default sort
Reply-by ascending; overdue pinned to top with a red accent.

### API endpoints consumed
```
GET    /api/tasks?status=open
POST   /api/tasks/:id/reply_by       { reply_by: ISO }
POST   /api/tasks/:id/status         { status: 'replied' | 'dismissed' | 'open' }
POST   /api/tasks/:id/feedback       { kind, note? }
POST   /api/poll                     -> triggers immediate poll
GET    /api/settings
POST   /api/settings                 { key, value }
```

---

## Evaluation plan
1. Before first release: user labels ~75 recent emails via `todo-mail label` (is_task y/n, summary, deadline). Stored as gold set in `eval/gold.jsonl`.
2. `todo-mail eval` runs the current prompt against the gold set, reports:
   - `is_task`: precision, recall, F1
   - `summary`: exact match + fuzzy match (rapidfuzz ratio ≥ 85)
   - `extracted_deadline`: within ±4h accuracy
   - Writes `eval/runs/{timestamp}.json` for run-over-run comparison
3. Shipping targets for v1: `is_task` recall ≥ 0.90, precision ≥ 0.70.
4. In-app feedback buttons append to the gold set over time.

---

## Locked defaults (override anytime via settings)
| Setting | Default |
|---|---|
| Reply-by window when no deadline extracted | 2 business days, 17:00 local |
| Gmail query filter | `in:inbox is:unread -category:promotions -category:social newer_than:7d` |
| Polling interval | 5 min |
| Reminder offsets | 24h, 1h, 0 (overdue) |
| Calendar | dedicated "Replies" calendar |

---

## Build order
1. Backend skeleton: FastAPI app, SQLite schema, Keychain wiring
2. Gmail OAuth + poll loop → `messages` table populated
3. Claude classifier + `tasks` creation
4. Vue 3 frontend scaffold (Vite + Tailwind), task list + inline reply-by editor
5. Reminders (APScheduler + pync)
6. Calendar integration (dedicated "Replies" calendar, CRUD on event per task status change)
7. Eval CLI (`label`, `eval`) + gold set of 75 emails
8. Packaging: `pipx`-installable, frontend bundled into wheel
