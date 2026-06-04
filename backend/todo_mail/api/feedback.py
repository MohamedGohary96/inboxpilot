from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_conn

router = APIRouter()

_VALID_KINDS = {"not_a_task", "wrong_summary", "wrong_deadline", "missed_task"}


class FeedbackBody(BaseModel):
    kind: str
    note: Optional[str] = None


@router.post("/tasks/{task_id}/feedback")
def add_feedback(task_id: int, body: FeedbackBody):
    if body.kind not in _VALID_KINDS:
        raise HTTPException(400, f"kind must be one of {_VALID_KINDS}")
    with get_conn() as conn:
        row = conn.execute("SELECT message_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "task not found")
        conn.execute(
            "INSERT INTO feedback (message_id, kind, note) VALUES (?, ?, ?)",
            (row["message_id"], body.kind, body.note),
        )
    return {"ok": True}
