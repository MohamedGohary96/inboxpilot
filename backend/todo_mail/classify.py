import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from .config import load as _load_config
from .db import get_conn
from .settings import get_secret, get_setting

logger = logging.getLogger(__name__)

# ── Provider-agnostic model / provider resolution ────────────────────────────

_PROVIDER_MODEL_DEFAULTS: dict[str, str] = {
    "groq":      "llama-3.3-70b-versatile",
    "openai":    "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
    "local":     "llama3",
}


def _provider_name() -> str:
    """Active provider name: settings DB → config.json → 'groq'."""
    return (
        (get_setting("llm_provider") or "").strip()
        or _load_config().get("llm_provider", "groq")
    )


def _model() -> str:
    """Active model ID: settings DB → config.json → per-provider default."""
    override = (get_setting("llm_model") or "").strip()
    if override:
        return override
    config_model = _load_config().get("model", "")
    if config_model:
        return config_model
    return _PROVIDER_MODEL_DEFAULTS.get(_provider_name(), "llama-3.3-70b-versatile")


def _prompt_version() -> str:
    return _load_config()["prompt_version"]


# ── API key caches (read once on the main thread to avoid macOS keychain
#    segfaults when keyring is called from worker threads) ───────────────────

_GROQ_API_KEY: str | None = get_secret("groq-api-key") or os.environ.get("GROQ_API_KEY")
_OPENAI_API_KEY: str | None = get_secret("openai-api-key") or os.environ.get("OPENAI_API_KEY")
_ANTHROPIC_API_KEY: str | None = get_secret("anthropic-api-key") or os.environ.get("ANTHROPIC_API_KEY")


def _get_provider():
    """Return an LLMProvider instance for the currently configured backend."""
    from .llm_providers import AnthropicProvider, GroqProvider, LocalProvider, OpenAIProvider

    name = _provider_name()
    model = _model()

    if name == "openai":
        if not _OPENAI_API_KEY:
            raise RuntimeError("No OpenAI API key — set one in Settings")
        return OpenAIProvider(_OPENAI_API_KEY, model)

    if name == "anthropic":
        if not _ANTHROPIC_API_KEY:
            raise RuntimeError("No Anthropic API key — set one in Settings")
        return AnthropicProvider(_ANTHROPIC_API_KEY, model)

    if name == "local":
        base_url = (
            (get_setting("llm_base_url") or "").strip()
            or _load_config().get("llm_base_url", "http://localhost:11434/v1")
        )
        return LocalProvider(model, base_url)

    # Default: groq
    if not _GROQ_API_KEY:
        raise RuntimeError("No Groq API key — set one in Settings or run 'todo-mail set-api-key'")
    return GroqProvider(_GROQ_API_KEY, model)


# ── Public key-management helpers ────────────────────────────────────────────

def has_provider_api_key(provider: str) -> bool:
    if provider == "groq":
        return bool(_GROQ_API_KEY)
    if provider == "openai":
        return bool(_OPENAI_API_KEY)
    if provider == "anthropic":
        return bool(_ANTHROPIC_API_KEY)
    if provider == "local":
        return True  # no key required
    return False


def set_provider_api_key(provider: str, key: str) -> None:
    """Persist key in OS keyring and update the in-process cache."""
    global _GROQ_API_KEY, _OPENAI_API_KEY, _ANTHROPIC_API_KEY
    from .settings import set_api_key as _set_api_key

    key = (key or "").strip()
    if not key:
        raise ValueError("API key is empty")
    _set_api_key(provider, key)

    if provider == "groq":
        _GROQ_API_KEY = key
    elif provider == "openai":
        _OPENAI_API_KEY = key
    elif provider == "anthropic":
        _ANTHROPIC_API_KEY = key


# Backwards-compatible aliases (used by CLI and legacy API endpoints)
def has_groq_api_key() -> bool:
    return has_provider_api_key("groq")


def set_groq_api_key(key: str) -> None:
    set_provider_api_key("groq", key)


# ── User identity ─────────────────────────────────────────────────────────────

def _user_identity() -> tuple[str, str]:
    """Return (display_name, email) for the signed-in user."""
    email = (get_setting("account_email") or "").strip() or "you@example.com"
    name = (get_setting("user_name") or "").strip()
    if not name:
        local = email.split("@", 1)[0]
        parts = re.split(r"[._\-+]+", local)
        name = " ".join(p.capitalize() for p in parts if p) or "User"
    return name, email


# ── Classification prompt + tool schema ───────────────────────────────────────

def _system_prompt() -> str:
    name, email = _user_identity()
    first = name.split()[0]
    return f"""You classify messages (emails or Slack DMs) as actionable tasks for {name} ({email}).

The message will be marked as either INCOMING (someone sent it to {first}) or OUTGOING ({first} sent it to someone else).

An INCOMING message IS a task if any of these apply:
- It asks a direct question that {first} is expected to answer
- It requests an action, decision, review, approval, or attendance from {first} specifically
- It is a meeting invite where {first} is a required attendee and has not responded
- It is a reply in a thread where the last message leaves the ball in {first}'s court

An INCOMING message is NOT a task if:
- It is a newsletter, marketing email, notification, or automated alert
- It is an FYI / CC where no action is requested of {first} specifically
- {first} is one of many recipients and no action is attributed to him individually
- It is a reply confirming or acknowledging something {first} already did
- The action is for someone else, not {first}

An OUTGOING message (sent BY {first}) IS a task ONLY when {first} himself committed to do something:
- {first} said "I'll do X", "I will send Y", "let me check Z"
- {first} proposed a meeting and committed to attend ("let's meet at 3pm", "I'll join the call")
- {first} said he would follow up, send something, review, or take an action himself

An OUTGOING message is NOT a task if:
- {first} is asking someone else to do something ("can you do X?", "please send me Y")
- {first} is delegating, requesting info, or asking a question
- {first} is just confirming, thanking, acknowledging, or chatting socially
- {first} only stated facts or opinions without committing to an action

For OUTGOING tasks, the asker should be set to "{name}" (self-commitment).

DEADLINE EXTRACTION — important:
- Treat the message's Date field as "today" when resolving relative dates.
- Resolve relative dates into ISO-8601 datetime (e.g. "2026-05-01T17:00:00").
- Examples (assume the message Date is Sunday 2026-04-26):
  - "by Friday" / "by next Friday" / "by 1 May" → 2026-05-01T17:00:00 (set deadline_confidence: explicit)
  - "tomorrow" → 2026-04-27T17:00:00 (explicit)
  - "by EOD" / "today" → same day, 17:00 (explicit)
  - "by end of week" → that week's Friday, 17:00 (implied)
  - "ASAP" / "soon" → null, deadline_confidence: none
- If a specific time of day is given ("by 3pm Friday"), use that exact time. Otherwise default to 17:00 (5pm).
- This applies BOTH to incoming requests ("can you send by Friday?") AND outgoing self-commitments ("I'll send by Friday").

Be conservative on negatives: if in doubt, mark is_task=true — {first} can dismiss it.
Always call the record_classification function with your result."""


_TOOL = {
    "type": "function",
    "function": {
        "name": "record_classification",
        "description": "Record the classification result for this email",
        "parameters": {
            "type": "object",
            "properties": {
                "is_task": {
                    "type": "boolean",
                    "description": "True if this email requires action from the recipient",
                },
                "reasoning": {
                    "type": "string",
                    "description": "One sentence explaining the classification",
                },
                "task_summary": {
                    "type": ["string", "null"],
                    "description": "One-line imperative summary, e.g. 'Review Q2 forecast deck' (null if not a task)",
                },
                "asker": {
                    "type": ["string", "null"],
                    "description": "Display name of the person requesting action (null if not identifiable)",
                },
                "extracted_deadline": {
                    "type": ["string", "null"],
                    "description": "ISO-8601 datetime if an explicit or clearly implied deadline exists, else null",
                },
                "deadline_confidence": {
                    "type": "string",
                    "enum": ["explicit", "implied", "none"],
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                },
                "priority_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Factors that influenced the priority rating",
                },
            },
            "required": ["is_task", "reasoning", "deadline_confidence", "priority", "priority_signals"],
        },
    },
}


# ── Result coercion ───────────────────────────────────────────────────────────

def _coerce(data: dict) -> dict:
    """Fix type mismatches that models occasionally produce."""
    if isinstance(data.get("is_task"), str):
        data["is_task"] = data["is_task"].lower() == "true"
    if isinstance(data.get("priority_signals"), str):
        try:
            data["priority_signals"] = json.loads(data["priority_signals"])
        except Exception:
            data["priority_signals"] = [data["priority_signals"]]
    for key in ("task_summary", "asker", "extracted_deadline"):
        if data.get(key) == "null":
            data[key] = None
    return data


# ── LLM call sites ────────────────────────────────────────────────────────────

def _call_llm(user_content: str) -> dict | None:
    try:
        provider = _get_provider()
    except RuntimeError as exc:
        logger.error("LLM provider unavailable: %s", exc)
        return None
    result = provider.chat_with_tool(_system_prompt(), user_content, _TOOL)
    return _coerce(result) if result else None


# ── Deadline helpers ──────────────────────────────────────────────────────────

def _default_reply_by(received_at_str: str | None) -> str:
    try:
        base = datetime.fromisoformat(received_at_str or "")
    except Exception:
        base = datetime.utcnow()

    days = int(get_setting("reply_by_days") or "2")
    hour = int(get_setting("reply_by_hour") or "17")

    result = base
    added = 0
    while added < days:
        result += timedelta(days=1)
        if result.weekday() not in (4, 5):  # skip Fri=4, Sat=5 (days off)
            added += 1

    return result.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def _vip_reply_by(received_at_str: str | None, window_hours: int) -> str:
    """Reply window for VIP senders: received_at + N hours, clamped past Fri/Sat
    days-off and never born overdue."""
    try:
        base = datetime.fromisoformat(received_at_str or "")
    except Exception:
        base = datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    deadline = base + timedelta(hours=window_hours)
    while deadline.weekday() in (4, 5):
        deadline += timedelta(days=1)
    now = datetime.now(timezone.utc)
    if deadline < now:
        deadline = now + timedelta(hours=1)
    return deadline.isoformat()


def _lookup_vip(sender_email: str | None) -> dict | None:
    """Return the priority_senders row matching this email (case-insensitive), or None."""
    if not sender_email:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, reply_window_hours FROM priority_senders"
            " WHERE email = ? COLLATE NOCASE LIMIT 1",
            (sender_email,),
        ).fetchone()
    return dict(row) if row else None


# ── Core classification ───────────────────────────────────────────────────────

def classify_and_store(message_id: int) -> bool:
    """Classify a stored message. Creates a task row if is_task=True. Returns True if task created."""
    with get_conn() as conn:
        if conn.execute(
            "SELECT id FROM classifications WHERE message_id = ?", (message_id,)
        ).fetchone():
            return False
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()

    if not msg:
        logger.warning("classify_and_store: message %d not found", message_id)
        return False

    # Skip LLM call for messages flagged by the pre-filter; record is_task=False so
    # this message is never retried.
    if msg["pre_filter_reason"]:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO classifications"
                " (message_id, model, prompt_version, is_task, raw_json)"
                " VALUES (?, ?, ?, 0, ?)",
                (
                    message_id,
                    "pre-filter",
                    _prompt_version(),
                    json.dumps({"pre_filter_reason": msg["pre_filter_reason"]}),
                ),
            )
        logger.debug("Pre-filtered message %d: %s", message_id, msg["pre_filter_reason"])
        return False

    slack_user_id = get_setting("slack_user_id")
    is_outgoing = (
        msg["source"] == "slack"
        and slack_user_id
        and msg["slack_sender_user_id"] == slack_user_id
    )

    user_name, user_email = _user_identity()
    first_name = user_name.split()[0]

    if is_outgoing:
        direction = f"OUTGOING (sent BY {first_name})"
        from_line = f"From: {user_name} (the user being classified for)"
        to_line = "To: someone else (the other party in the DM)"
    else:
        direction = f"INCOMING (sent TO {first_name})"
        to_line = f"To: {user_name} <{user_email}>"
        from_line = (
            f"From: {msg['sender']} <{msg['sender_email']}>"
            if msg["sender_email"]
            else f"From: {msg['sender']}"
        )

    user_content = (
        f"Direction: {direction}\n"
        f"{to_line}\n"
        f"{from_line}\n"
        f"Subject: {msg['subject']}\n"
        f"Date: {msg['received_at']}\n"
        f"---\n"
        f"{(msg['body_text'] or '')[:8000]}"
    )

    result = _call_llm(user_content)
    if not result:
        logger.warning("LLM returned no result for message %d", message_id)
        return False

    is_task: bool = bool(result.get("is_task", False))
    task_id: int | None = None
    reply_by_str: str | None = None

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO classifications (message_id, model, prompt_version, is_task, raw_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (message_id, _model(), _prompt_version(), is_task, json.dumps(result)),
        )

        if is_task:
            extracted_deadline: str | None = result.get("extracted_deadline")
            priority = result.get("priority", "normal")

            sender_email_for_match = msg["sender_email"] if msg["source"] != "slack" else msg["slack_sender_email"]
            vip = _lookup_vip(sender_email_for_match)
            if vip:
                priority = "high"
                reply_by_str = extracted_deadline or _vip_reply_by(msg["received_at"], int(vip["reply_window_hours"]))
            else:
                reply_by_str = extracted_deadline or _default_reply_by(msg["received_at"])

            task_source = "slack" if msg["source"] == "slack" else "mail"
            conn.execute(
                "INSERT OR IGNORE INTO tasks"
                " (message_id, source, summary, asker, extracted_deadline, priority, reply_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message_id,
                    task_source,
                    result.get("task_summary"),
                    result.get("asker"),
                    extracted_deadline,
                    priority,
                    reply_by_str,
                ),
            )
            row = conn.execute(
                "SELECT id FROM tasks WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row:
                task_id = row["id"]
            logger.info("Task created for message %d: %s", message_id, result.get("task_summary"))

    if task_id and reply_by_str:
        _post_task_created(task_id, reply_by_str, dict(msg), result.get("task_summary"))

    return is_task


# ── Action-intent parsing (for smart-reply) ───────────────────────────────────

def parse_action_intent(instructions: str) -> dict:
    """Use the LLM to detect meeting intent and extract structured params."""
    from datetime import date as _date
    today = _date.today().isoformat()

    system = (
        f"Today is {today}. Extract the user's intent from their instruction.\n"
        "Reply with ONLY valid JSON, no extra text.\n\n"
        "Schema:\n"
        "{\n"
        '  "has_meeting": true | false,\n'
        '  "date": "YYYY-MM-DD" or null,\n'
        '  "time": "HH:MM" or null,\n'
        '  "duration_minutes": integer (default 30),\n'
        '  "reply_instructions": string  // what to say in the email reply; if meeting, include a note about it\n'
        "}\n\n"
        "Rules:\n"
        "- Set has_meeting=true only when the instruction is about booking/scheduling a meeting or call.\n"
        "- Convert relative dates (tomorrow, next Monday, etc.) to absolute YYYY-MM-DD using today's date.\n"
        "- Convert 12-hour times (11 AM, 3 PM) to 24-hour HH:MM.\n"
        "- If no meeting is mentioned, set has_meeting=false, date/time/duration to null/30.\n"
        "- reply_instructions should be a concise directive for drafting the email."
    )

    _default = {
        "has_meeting": False,
        "date": None,
        "time": None,
        "duration_minutes": 30,
        "reply_instructions": instructions,
    }

    try:
        provider = _get_provider()
    except RuntimeError as exc:
        logger.error("LLM provider unavailable: %s", exc)
        return _default

    try:
        raw = provider.chat(system, instructions, json_mode=True) or "{}"
        data = json.loads(raw)
        return {
            "has_meeting":        bool(data.get("has_meeting", False)),
            "date":               data.get("date"),
            "time":               data.get("time"),
            "duration_minutes":   int(data.get("duration_minutes") or 30),
            "reply_instructions": str(data.get("reply_instructions") or instructions),
        }
    except Exception:
        logger.exception("parse_action_intent error")
        return _default


# ── Reply drafting ────────────────────────────────────────────────────────────

def suggest_reply_draft(message_id: int, instructions: str | None = None) -> str | None:
    """Generate a draft reply for a task message (email or Slack). Returns plain text or None."""
    with get_conn() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not msg:
        return None

    is_slack = msg["source"] == "slack"
    instructions = (instructions or "").strip()[:500] or None

    user_name, user_email = _user_identity()
    first_name = user_name.split()[0]

    if is_slack:
        system = (
            f"You are a ghostwriter for {user_name}.\n"
            f"Write a Slack reply in {first_name}'s voice.\n"
            "- Follow the INSTRUCTION exactly — it is the primary directive\n"
            "- Match Slack's informal tone — short, no formal greeting or sign-off\n"
            "- Address the specific request or question directly\n"
            "- Output ONLY the reply text, nothing else"
        )
        from_line = f"From: {msg['sender']}"
    else:
        system = (
            f"You are a ghostwriter for {user_name} ({user_email}).\n"
            f"Write a complete, send-ready email reply in {first_name}'s voice.\n"
            "- Follow the INSTRUCTION exactly — it is the primary directive\n"
            "- Address the sender's specific request or question directly\n"
            "- Be concise and professional, but friendly\n"
            f"- Include a greeting (e.g. 'Hi [Name],') and sign-off ('Best,\\n{first_name}')\n"
            "- Output ONLY the reply body — no subject line, no metadata, no explanations\n"
            "- Never invent facts not present in the email or instruction"
        )
        from_line = f"From: {msg['sender']} <{msg['sender_email']}>"

    instruction_line = f"INSTRUCTION: {instructions}" if instructions else "INSTRUCTION: Write a helpful, professional reply."
    user_content = (
        f"{instruction_line}\n\n"
        f"---\n"
        f"{from_line}\n"
        f"Subject: {msg['subject']}\n"
        f"Date: {msg['received_at']}\n"
        f"---\n"
        f"{(msg['body_text'] or '')[:6000]}"
    )

    try:
        provider = _get_provider()
    except RuntimeError as exc:
        logger.error("LLM provider unavailable: %s", exc)
        return None

    return provider.chat(system, user_content)


# ── News summarisation ────────────────────────────────────────────────────────

def summarize_news(message_id: int) -> str | None:
    """Generate a one-line LLM summary of a news message and cache it on the row."""
    with get_conn() as conn:
        msg = conn.execute(
            "SELECT subject, body_text, news_summary FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
    if not msg:
        return None
    if msg["news_summary"]:
        return msg["news_summary"]

    system = (
        "You summarize GitHub notification emails (releases, security advisories, "
        "discussions, newsletters) for a busy engineer.\n"
        "- Output ONE sentence, max 18 words.\n"
        "- No quotes, no prefix, no markdown. Just the summary text.\n"
        "- Focus on what's new or actionable, not metadata."
    )
    user = (
        f"Subject: {msg['subject']}\n\n"
        f"{(msg['body_text'] or '')[:2500]}"
    )

    try:
        provider = _get_provider()
    except RuntimeError as exc:
        logger.error("LLM provider unavailable: %s", exc)
        return None

    raw = provider.chat(system, user)
    if not raw:
        return None
    summary = raw.strip().strip('"').strip("'")[:240]
    if not summary:
        return None

    with get_conn() as conn:
        conn.execute(
            "UPDATE messages SET news_summary = ? WHERE id = ?",
            (summary, message_id),
        )
    return summary


# ── Eval helper ───────────────────────────────────────────────────────────────

def classify_for_eval(message_id: int) -> dict | None:
    """Run classification without storing anything. Used by the eval CLI."""
    with get_conn() as conn:
        msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    if not msg:
        return None

    user_name, user_email = _user_identity()
    user_content = (
        f"To: {user_name} <{user_email}>\n"
        f"From: {msg['sender']} <{msg['sender_email']}>\n"
        f"Subject: {msg['subject']}\n"
        f"Date: {msg['received_at']}\n"
        f"---\n"
        f"{(msg['body_text'] or '')[:8000]}"
    )
    return _call_llm(user_content)


# ── Post-task hooks ───────────────────────────────────────────────────────────

def _post_task_created(
    task_id: int,
    reply_by_str: str,
    msg: dict,
    task_summary: str | None,
) -> None:
    try:
        from .scheduler import schedule_reminders
        schedule_reminders(task_id)
    except Exception:
        logger.warning("Could not schedule reminders for task %d", task_id)

    try:
        from .calendar_client import get_calendar
        cal = get_calendar()
        if not cal:
            return
        reply_by_dt = datetime.fromisoformat(reply_by_str)
        event_id = cal.create_event(
            task_id=task_id,
            subject=msg.get("subject") or "(no subject)",
            summary=task_summary,
            reply_by=reply_by_dt,
            thread_id=msg.get("thread_id") or "",
        )
        with get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET calendar_event_id = ? WHERE id = ?",
                (event_id, task_id),
            )
    except Exception:
        logger.warning("Could not create calendar event for task %d", task_id)
