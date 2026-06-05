import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── DB fixture: redirect every test to a fresh in-memory SQLite ──────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("todo_mail.db.DB_PATH", db_file)
    # Also patch any module that imported DB_PATH directly
    import todo_mail.db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    from todo_mail.db import init_db
    init_db()
    yield db_file


# ── Keychain: never hit the real macOS keychain ───────────────────────────────

@pytest.fixture(autouse=True)
def no_keychain(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda *a, **kw: None)
    monkeypatch.setattr("keyring.set_password", lambda *a, **kw: None)
    monkeypatch.setattr("keyring.delete_password", lambda *a, **kw: None)


# ── Groq mock factory ────────────────────────────────────────────────────────

def make_classification(is_task: bool = True, summary: str = "Test task") -> dict:
    return {
        "is_task": is_task,
        "reasoning": "Direct question requiring a reply.",
        "task_summary": summary if is_task else None,
        "asker": "Alice",
        "extracted_deadline": None,
        "deadline_confidence": "none",
        "priority": "normal",
        "priority_signals": ["direct question"],
    }


@pytest.fixture
def mock_groq(monkeypatch):
    """Patch _get_provider so classify tests never hit the network or keychain.

    Named `mock_groq` for backwards compatibility with existing tests, but it
    now returns a mock LLMProvider whose `chat_with_tool` returns a parsed
    classification dict directly. Tests assert against
    `mock_groq.chat_with_tool.call_count` / `.assert_not_called()`.
    """
    provider = MagicMock()
    provider.chat_with_tool.return_value = make_classification()
    monkeypatch.setattr("todo_mail.classify._get_provider", lambda: provider)
    return provider


# Legacy alias kept so future tests can use a clearer name without breaking
# old ones.
@pytest.fixture
def mock_provider(mock_groq):
    return mock_groq


# ── Minimal message row helper ────────────────────────────────────────────────

def insert_message(conn, gmail_id: str = "msg1", sender_email: str = "alice@example.com",
                   subject: str = "Hello", body: str = "Can you review this?",
                   pre_filter_reason: str | None = None) -> int:
    conn.execute(
        """INSERT INTO messages
           (gmail_message_id, thread_id, sender, sender_email, subject,
            received_at, snippet, body_text, processed_at, pre_filter_reason)
           VALUES (?, ?, ?, ?, ?, datetime('now','-1 hour'), ?, ?, CURRENT_TIMESTAMP, ?)""",
        (gmail_id, "thread1", "Alice", sender_email, subject, body[:100], body, pre_filter_reason),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── FastAPI test client (no lifespan — avoids Gmail/Calendar init) ────────────

@pytest.fixture
def client():
    from todo_mail.app import app
    # TestClient runs lifespan by default; we skip it to avoid credential prompts
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
