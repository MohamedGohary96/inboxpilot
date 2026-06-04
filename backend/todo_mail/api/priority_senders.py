import re
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_conn

router = APIRouter()

# Match a local-part@domain.tld with at least one dot in the domain. Loose by
# design — Slack/Gmail accept many shapes; we just want to reject @acme.com or
# bare strings that obviously aren't an email.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_REPLY_WINDOW_MIN = 1
_REPLY_WINDOW_MAX = 24 * 7  # one week
_NOTE_MAX_CHARS = 200


def _validate_email(email: str) -> str:
    e = email.strip()
    if not _EMAIL_RE.match(e):
        raise HTTPException(400, "must be a full email address (e.g. alice@acme.com)")
    return e


def _validate_window(hours: int) -> int:
    if hours < _REPLY_WINDOW_MIN or hours > _REPLY_WINDOW_MAX:
        raise HTTPException(400, f"reply_window_hours must be between {_REPLY_WINDOW_MIN} and {_REPLY_WINDOW_MAX}")
    return hours


class SenderCreate(BaseModel):
    email: str
    note: str | None = None
    reply_window_hours: int = 4


class SenderUpdate(BaseModel):
    note: str | None = None
    reply_window_hours: int | None = None


@router.get("/priority-senders")
def list_senders():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, note, reply_window_hours, created_at"
            " FROM priority_senders ORDER BY email COLLATE NOCASE ASC"
        ).fetchall()
    return {"senders": [dict(r) for r in rows]}


@router.post("/priority-senders", status_code=201)
def add_sender(body: SenderCreate):
    email = _validate_email(body.email)
    window = _validate_window(body.reply_window_hours)
    note = (body.note or "").strip() or None
    if note and len(note) > _NOTE_MAX_CHARS:
        raise HTTPException(400, f"note must be ≤ {_NOTE_MAX_CHARS} characters")

    with get_conn() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO priority_senders (email, note, reply_window_hours)"
                " VALUES (?, ?, ?)",
                (email, note, window),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, f"{email} is already a priority sender")
        row = conn.execute(
            "SELECT id, email, note, reply_window_hours, created_at"
            " FROM priority_senders WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


@router.patch("/priority-senders/{sender_id}")
def update_sender(sender_id: int, body: SenderUpdate):
    updates, values = [], []
    if body.note is not None:
        note = body.note.strip() or None
        if note and len(note) > _NOTE_MAX_CHARS:
            raise HTTPException(400, f"note must be ≤ {_NOTE_MAX_CHARS} characters")
        updates.append("note = ?")
        values.append(note)
    if body.reply_window_hours is not None:
        updates.append("reply_window_hours = ?")
        values.append(_validate_window(body.reply_window_hours))
    if not updates:
        raise HTTPException(400, "nothing to update")

    values.append(sender_id)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE priority_senders SET {', '.join(updates)} WHERE id = ?",
            tuple(values),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "sender not found")
    return {"ok": True}


@router.delete("/priority-senders/{sender_id}")
def delete_sender(sender_id: int):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM priority_senders WHERE id = ?", (sender_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "sender not found")
    return {"ok": True}
