from datetime import datetime, date, time, timedelta

from typing import List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import get_conn

router = APIRouter()

_VALID_STATUSES = {"open", "replied", "dismissed"}

_LIST_SQL = """
    SELECT
        t.id, t.source, t.title, t.notes,
        t.summary, t.asker, t.extracted_deadline, t.priority, t.completion,
        t.reply_by, t.status, t.calendar_event_id, t.created_at, t.updated_at,
        m.sender, m.sender_email, m.subject, m.thread_id, m.received_at,
        m.slack_channel_id, m.slack_ts, m.slack_team_id, m.sender_avatar,
        COALESCE(l.c, 0) AS link_count,
        (ps.id IS NOT NULL) AS is_vip_sender
    FROM tasks t
    LEFT JOIN messages m ON t.message_id = m.id
    LEFT JOIN (
        SELECT task_id, COUNT(*) AS c FROM task_links GROUP BY task_id
    ) l ON l.task_id = t.id
    LEFT JOIN priority_senders ps
        ON ps.email = COALESCE(m.sender_email, m.slack_sender_email) COLLATE NOCASE
    {where}
    ORDER BY
        CASE WHEN t.reply_by < datetime('now') THEN 0 ELSE 1 END,
        t.reply_by ASC
"""

_VALID_COMPLETIONS = {"not_started", "in_progress", "on_hold", "completed"}
_NOTES_MAX_CHARS = 50_000
_URL_MAX_CHARS = 2048
_LABEL_MAX_CHARS = 200
_LINKS_PER_TASK_CAP = 50


@router.get("/tasks")
def list_tasks(
    status: str = "open",
    source: List[str] = Query(default=[]),
    priority: List[str] = Query(default=[]),
    completion: List[str] = Query(default=[]),
    reply_by: str | None = None,
):
    conditions: list[str] = []
    params: list = []

    if status != "all":
        conditions.append("t.status = ?")
        params.append(status)

    if source:
        placeholders = ",".join("?" * len(source))
        conditions.append(f"t.source IN ({placeholders})")
        params.extend(source)

    if priority:
        placeholders = ",".join("?" * len(priority))
        conditions.append(f"t.priority IN ({placeholders})")
        params.extend(priority)

    if completion:
        placeholders = ",".join("?" * len(completion))
        conditions.append(f"t.completion IN ({placeholders})")
        params.extend(completion)

    if reply_by == "overdue":
        conditions.append("t.reply_by IS NOT NULL AND t.reply_by < datetime('now')")
    elif reply_by == "today":
        conditions.append("date(t.reply_by) = date('now')")
    elif reply_by == "week":
        conditions.append("t.reply_by IS NOT NULL AND t.reply_by BETWEEN datetime('now') AND datetime('now', '+7 days')")
    elif reply_by == "month":
        conditions.append("t.reply_by IS NOT NULL AND t.reply_by BETWEEN datetime('now') AND datetime('now', '+30 days')")
    elif reply_by == "none":
        conditions.append("t.reply_by IS NULL")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = _LIST_SQL.format(where=where)

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


class TaskCreate(BaseModel):
    title: str
    reply_by: datetime | None = None
    priority: str = "normal"
    notes: str | None = None


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate):
    if not body.title.strip():
        raise HTTPException(400, "title is required")
    if body.priority not in ("low", "normal", "high"):
        raise HTTPException(400, "priority must be low, normal, or high")

    reply_by = body.reply_by
    if reply_by is None:
        tomorrow = date.today() + timedelta(days=1)
        reply_by = datetime.combine(tomorrow, time(17, 0))

    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO tasks (source, title, notes, priority, reply_by, status)
               VALUES ('manual', ?, ?, ?, ?, 'open')""",
            (body.title.strip(), body.notes, body.priority, reply_by.isoformat()),
        )
        task_id = cursor.lastrowid
        row = conn.execute(
            """SELECT t.id, t.source, t.title, t.notes,
                      t.summary, t.asker, t.extracted_deadline, t.priority, t.completion,
                      t.reply_by, t.status, t.calendar_event_id, t.created_at, t.updated_at,
                      NULL as sender, NULL as sender_email, NULL as subject,
                      NULL as thread_id, NULL as received_at,
                      0 as link_count,
                      0 as is_vip_sender
               FROM tasks t WHERE t.id = ?""",
            (task_id,),
        ).fetchone()
    return dict(row)


class TaskUpdate(BaseModel):
    title: str | None = None
    priority: str | None = None
    completion: str | None = None
    notes: str | None = None


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    if body.priority and body.priority not in ("low", "normal", "high"):
        raise HTTPException(400, "priority must be low, normal, or high")
    if body.completion and body.completion not in _VALID_COMPLETIONS:
        raise HTTPException(400, f"completion must be one of {_VALID_COMPLETIONS}")
    if body.notes is not None and len(body.notes) > _NOTES_MAX_CHARS:
        raise HTTPException(400, f"notes must be ≤ {_NOTES_MAX_CHARS} characters")

    updates, values = [], []
    if body.title is not None:
        updates.append("title = ?")
        values.append(body.title.strip() or None)
    if body.priority is not None:
        updates.append("priority = ?")
        values.append(body.priority)
    if body.completion is not None:
        updates.append("completion = ?")
        values.append(body.completion)
    if body.notes is not None:
        updates.append("notes = ?")
        values.append(body.notes or None)
    if not updates:
        raise HTTPException(400, "nothing to update")

    values.append(task_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tasks SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            tuple(values),
        )
    return {"ok": True}


class ReplyByUpdate(BaseModel):
    reply_by: datetime


@router.post("/tasks/{task_id}/reply_by")
def update_reply_by(task_id: int, body: ReplyByUpdate):
    with get_conn() as conn:
        task = conn.execute(
            "SELECT calendar_event_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not task:
            raise HTTPException(404, "task not found")
        conn.execute(
            "UPDATE tasks SET reply_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (body.reply_by.isoformat(), task_id),
        )

    event_id: str | None = task["calendar_event_id"]
    if event_id:
        try:
            from ..calendar_client import get_calendar
            cal = get_calendar()
            if cal:
                cal.update_event(event_id, body.reply_by)
        except Exception:
            pass

    try:
        from ..scheduler import cancel_reminders, schedule_reminders
        cancel_reminders(task_id)
        schedule_reminders(task_id)
    except Exception:
        pass

    return {"ok": True}


class StatusUpdate(BaseModel):
    status: str


@router.post("/tasks/{task_id}/status")
def update_status(task_id: int, body: StatusUpdate):
    if body.status not in _VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {_VALID_STATUSES}")

    with get_conn() as conn:
        task = conn.execute(
            "SELECT calendar_event_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not task:
            raise HTTPException(404, "task not found")
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (body.status, task_id),
        )

    if body.status in ("replied", "dismissed"):
        event_id = task["calendar_event_id"]
        if event_id:
            try:
                from ..calendar_client import get_calendar
                cal = get_calendar()
                if cal:
                    cal.delete_event(event_id)
            except Exception:
                pass
        try:
            from ..scheduler import cancel_reminders
            cancel_reminders(task_id)
        except Exception:
            pass

    return {"ok": True}


# ── Task links ────────────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    url: str
    label: str | None = None


def _validate_link(url: str, label: str | None) -> tuple[str, str | None]:
    url = url.strip()
    if not url:
        raise HTTPException(400, "url is required")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(400, "url must start with http:// or https://")
    if len(url) > _URL_MAX_CHARS:
        raise HTTPException(400, f"url must be ≤ {_URL_MAX_CHARS} characters")
    label = (label or "").strip() or None
    if label and len(label) > _LABEL_MAX_CHARS:
        raise HTTPException(400, f"label must be ≤ {_LABEL_MAX_CHARS} characters")
    return url, label


@router.get("/tasks/{task_id}/links")
def list_links(task_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, url, label, created_at FROM task_links"
            " WHERE task_id = ? ORDER BY created_at ASC, id ASC",
            (task_id,),
        ).fetchall()
    return {"links": [dict(r) for r in rows]}


@router.post("/tasks/{task_id}/links", status_code=201)
def add_link(task_id: int, body: LinkCreate):
    url, label = _validate_link(body.url, body.label)
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
            raise HTTPException(404, "task not found")
        count = conn.execute(
            "SELECT COUNT(*) FROM task_links WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        if count >= _LINKS_PER_TASK_CAP:
            raise HTTPException(400, f"task already has {_LINKS_PER_TASK_CAP} links")
        cursor = conn.execute(
            "INSERT INTO task_links (task_id, url, label) VALUES (?, ?, ?)",
            (task_id, url, label),
        )
        row = conn.execute(
            "SELECT id, url, label, created_at FROM task_links WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


@router.delete("/tasks/{task_id}/links/{link_id}")
def delete_link(task_id: int, link_id: int):
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM task_links WHERE id = ? AND task_id = ?",
            (link_id, task_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "link not found")
    return {"ok": True}


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.post("/admin/reload-config")
def reload_config():
    from ..config import reload as _reload
    cfg = _reload()
    return {"model": cfg["model"], "prompt_version": cfg["prompt_version"]}


@router.get("/admin/llm-calls")
def list_llm_calls(limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.model, c.prompt_version, c.is_task,
                      c.raw_json, c.created_at,
                      m.subject, m.sender, m.sender_email
               FROM classifications c
               JOIN messages m ON c.message_id = m.id
               WHERE c.model != 'pre-filter'
               ORDER BY c.created_at DESC
               LIMIT ?""",
            (min(limit, 100),),
        ).fetchall()

    import json as _json
    result = []
    for row in rows:
        raw = _json.loads(row["raw_json"] or "{}")
        result.append({
            "id":               row["id"],
            "model":            row["model"],
            "prompt_version":   row["prompt_version"],
            "is_task":          bool(row["is_task"]),
            "reasoning":        raw.get("reasoning"),
            "priority":         raw.get("priority"),
            "priority_signals": raw.get("priority_signals", []),
            "deadline_confidence": raw.get("deadline_confidence"),
            "classified_at":    row["created_at"],
            "subject":          row["subject"],
            "sender":           row["sender"],
            "sender_email":     row["sender_email"],
        })
    return result


@router.get("/tasks/{task_id}/classification")
def get_classification(task_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT c.raw_json, c.model, c.prompt_version, c.created_at
               FROM classifications c
               JOIN tasks t ON t.message_id = c.message_id
               WHERE t.id = ?
               ORDER BY c.created_at DESC LIMIT 1""",
            (task_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "no classification found")

    import json as _json
    raw = _json.loads(row["raw_json"] or "{}")
    return {
        "reasoning":          raw.get("reasoning"),
        "priority_signals":   raw.get("priority_signals", []),
        "deadline_confidence": raw.get("deadline_confidence"),
        "model":              row["model"],
        "prompt_version":     row["prompt_version"],
        "classified_at":      row["created_at"],
    }


@router.post("/tasks/{task_id}/suggest-reply")
def suggest_reply(task_id: int):
    with get_conn() as conn:
        task = conn.execute(
            "SELECT message_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if not task:
        raise HTTPException(404, "task not found")

    from ..classify import suggest_reply_draft
    draft = suggest_reply_draft(task["message_id"])
    if not draft:
        raise HTTPException(503, "LLM unavailable")
    return {"reply": draft}


class DraftReplyRequest(BaseModel):
    instructions: str | None = None


class SmartReplyRequest(BaseModel):
    instructions: str


class ScheduleMeetingRequest(BaseModel):
    date: str                       # YYYY-MM-DD
    window_start: str = "09:00"     # HH:MM local time
    window_end: str = "12:00"       # HH:MM local time
    duration_minutes: int = 30
    title: str | None = None


@router.post("/tasks/{task_id}/draft-reply")
def draft_reply(task_id: int, body: DraftReplyRequest):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.message_id, m.sender_email, m.subject, m.thread_id
               FROM tasks t LEFT JOIN messages m ON m.id = t.message_id
               WHERE t.id = ?""",
            (task_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "task not found")

    from ..classify import suggest_reply_draft
    draft = suggest_reply_draft(row["message_id"], body.instructions)
    if not draft:
        raise HTTPException(503, "LLM unavailable")
    return {
        "draft": draft,
        "to_email": row["sender_email"],
        "subject": row["subject"],
        "thread_id": row["thread_id"],
    }


@router.post("/tasks/{task_id}/schedule-meeting")
def schedule_task_meeting(task_id: int, body: ScheduleMeetingRequest):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.id,
                      COALESCE(m.sender_email, m.slack_sender_email) AS sender_email,
                      m.sender
               FROM tasks t LEFT JOIN messages m ON m.id = t.message_id
               WHERE t.id = ?""",
            (task_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "task not found")
    if not row["sender_email"]:
        raise HTTPException(400, "no sender email found for this task")

    from ..calendar_client import get_calendar
    cal = get_calendar()
    if not cal:
        raise HTTPException(503, "Google Calendar not connected")

    title = (body.title or "").strip() or f"Meeting with {row['sender'] or row['sender_email']}"

    try:
        result = cal.find_and_book_meeting(
            date_str=body.date,
            window_start=body.window_start,
            window_end=body.window_end,
            duration_minutes=body.duration_minutes,
            title=title,
            attendee_email=row["sender_email"],
            attendee_name=row["sender"],
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    return result


@router.post("/tasks/{task_id}/smart-reply")
def smart_reply(task_id: int, body: SmartReplyRequest):
    """Parse free-text instructions, optionally book a meeting, always draft a reply."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.message_id,
                      COALESCE(m.sender_email, m.slack_sender_email) AS sender_email,
                      m.sender, m.subject, m.thread_id
               FROM tasks t LEFT JOIN messages m ON m.id = t.message_id
               WHERE t.id = ?""",
            (task_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "task not found")

    from ..classify import parse_action_intent, suggest_reply_draft
    intent = parse_action_intent(body.instructions)

    meeting_result = None
    if intent["has_meeting"]:
        if not intent["date"] or not intent["time"]:
            meeting_result = {"error": "Could not parse the meeting date or time from your instructions."}
        elif not row["sender_email"]:
            meeting_result = {"error": "No email address found for this sender — cannot send a calendar invite."}
        else:
            from ..calendar_client import get_calendar
            cal = get_calendar()
            if not cal:
                meeting_result = {"error": "Calendar not available — please reconnect Google."}
            else:
                try:
                    h, m_min = map(int, intent["time"].split(":"))
                    dur = intent["duration_minutes"]
                    end_h, end_m = divmod(h * 60 + m_min + dur, 60)
                    window_end = f"{end_h:02d}:{end_m:02d}"

                    title = f"Meeting with {row['sender'] or row['sender_email']}"
                    meeting_result = cal.find_and_book_meeting(
                        date_str=intent["date"],
                        window_start=intent["time"],
                        window_end=window_end,
                        duration_minutes=dur,
                        title=title,
                        attendee_email=row["sender_email"],
                        attendee_name=row["sender"],
                    )
                except Exception as exc:
                    meeting_result = {"error": str(exc)}

    draft = suggest_reply_draft(row["message_id"], intent["reply_instructions"])
    if not draft:
        raise HTTPException(503, "LLM unavailable")

    return {
        "draft": draft,
        "meeting": meeting_result,
        "to_email": row["sender_email"],
        "subject": row["subject"],
        "thread_id": row["thread_id"],
    }
