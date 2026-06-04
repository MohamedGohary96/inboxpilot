import pytest
from todo_mail.db import get_conn
from tests.conftest import insert_message


def _seed_task(conn, gmail_id: str = "msg1", status: str = "open") -> tuple[int, int]:
    """Insert a message + classification + task. Returns (message_id, task_id)."""
    import json
    msg_id = insert_message(conn, gmail_id=gmail_id)
    conn.execute(
        "INSERT INTO classifications (message_id, model, prompt_version, is_task, raw_json)"
        " VALUES (?, ?, ?, 1, ?)",
        (msg_id, "llama-test", "v1", json.dumps({
            "reasoning": "Direct question.",
            "priority_signals": ["direct question"],
            "deadline_confidence": "none",
        })),
    )
    conn.execute(
        "INSERT INTO tasks (message_id, summary, priority, reply_by, status)"
        " VALUES (?, ?, ?, datetime('now','+2 days'), ?)",
        (msg_id, "Test task", "normal", status),
    )
    task_id = conn.execute("SELECT id FROM tasks WHERE message_id = ?", (msg_id,)).fetchone()[0]
    return msg_id, task_id


# ── GET /api/tasks ────────────────────────────────────────────────────────────

def test_list_tasks_default_open(client):
    with get_conn() as conn:
        _, _ = _seed_task(conn, "msg1", "open")
        _, _ = _seed_task(conn, "msg2", "replied")

    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "open"


def test_list_tasks_all(client):
    with get_conn() as conn:
        _seed_task(conn, "msg1", "open")
        _seed_task(conn, "msg2", "dismissed")

    resp = client.get("/api/tasks?status=all")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── POST /api/tasks/:id/reply_by ─────────────────────────────────────────────

def test_update_reply_by(client):
    with get_conn() as conn:
        _, task_id = _seed_task(conn)

    resp = client.post(
        f"/api/tasks/{task_id}/reply_by",
        json={"reply_by": "2030-01-15T17:00:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    with get_conn() as conn:
        row = conn.execute("SELECT reply_by FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert "2030-01-15" in row["reply_by"]


def test_update_reply_by_404(client):
    resp = client.post("/api/tasks/9999/reply_by", json={"reply_by": "2030-01-01T00:00:00"})
    assert resp.status_code == 404


# ── POST /api/tasks/:id/status ────────────────────────────────────────────────

def test_mark_replied(client):
    with get_conn() as conn:
        _, task_id = _seed_task(conn)

    resp = client.post(f"/api/tasks/{task_id}/status", json={"status": "replied"})
    assert resp.status_code == 200

    with get_conn() as conn:
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    assert row["status"] == "replied"


def test_invalid_status_rejected(client):
    with get_conn() as conn:
        _, task_id = _seed_task(conn)

    resp = client.post(f"/api/tasks/{task_id}/status", json={"status": "flying"})
    assert resp.status_code == 400


# ── GET /api/tasks/:id/classification ────────────────────────────────────────

def test_get_classification(client):
    with get_conn() as conn:
        _, task_id = _seed_task(conn)

    resp = client.get(f"/api/tasks/{task_id}/classification")
    assert resp.status_code == 200
    data = resp.json()
    assert data["reasoning"] == "Direct question."
    assert "direct question" in data["priority_signals"]
    assert data["deadline_confidence"] == "none"


def test_get_classification_404(client):
    resp = client.get("/api/tasks/9999/classification")
    assert resp.status_code == 404


# ── POST /api/tasks/:id/feedback ─────────────────────────────────────────────

def test_add_feedback(client):
    with get_conn() as conn:
        msg_id, task_id = _seed_task(conn)

    resp = client.post(f"/api/tasks/{task_id}/feedback", json={"kind": "wrong_deadline"})
    assert resp.status_code == 200

    with get_conn() as conn:
        row = conn.execute("SELECT kind FROM feedback WHERE message_id = ?", (msg_id,)).fetchone()
    assert row["kind"] == "wrong_deadline"


def test_invalid_feedback_kind_rejected(client):
    with get_conn() as conn:
        _, task_id = _seed_task(conn)

    resp = client.post(f"/api/tasks/{task_id}/feedback", json={"kind": "totally_made_up"})
    assert resp.status_code == 400


# ── GET /api/status ───────────────────────────────────────────────────────────

def test_status_unauthenticated(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["total_messages"] == 0


# ── GET /api/metrics ─────────────────────────────────────────────────────────

def test_metrics_empty(client):
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["median_reply_latency_hours"] is None
    assert data["open_overdue_count"] == 0
    assert data["trust_index_dismissals_per_100"] is None
