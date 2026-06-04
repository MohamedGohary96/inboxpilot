import pytest
from todo_mail.db import get_conn
from todo_mail.classify import classify_and_store
from tests.conftest import insert_message


def test_task_created_when_llm_returns_is_task_true(mock_groq):
    with get_conn() as conn:
        msg_id = insert_message(conn)

    result = classify_and_store(msg_id)

    assert result is True
    with get_conn() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE message_id = ?", (msg_id,)).fetchone()
        clf = conn.execute("SELECT * FROM classifications WHERE message_id = ?", (msg_id,)).fetchone()

    assert task is not None
    assert task["summary"] == "Test task"
    assert task["status"] == "open"
    assert clf["is_task"] == 1


def test_no_task_when_llm_returns_not_a_task(mock_groq):
    mock_groq.chat.completions.create.return_value.__class__  # ensure it's a mock
    import json
    from unittest.mock import MagicMock
    args = {
        "is_task": False, "reasoning": "FYI only", "task_summary": None,
        "asker": None, "extracted_deadline": None,
        "deadline_confidence": "none", "priority": "low", "priority_signals": [],
    }
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(args)
    msg = MagicMock()
    msg.tool_calls = [tool_call]
    mock_groq.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=msg)])

    with get_conn() as conn:
        msg_id = insert_message(conn, gmail_id="msg2")

    result = classify_and_store(msg_id)

    assert result is False
    with get_conn() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE message_id = ?", (msg_id,)).fetchone()
    assert task is None


def test_idempotent_second_call(mock_groq):
    with get_conn() as conn:
        msg_id = insert_message(conn)

    classify_and_store(msg_id)
    classify_and_store(msg_id)  # second call — should no-op

    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM classifications WHERE message_id = ?", (msg_id,)
        ).fetchone()[0]
    assert count == 1
    assert mock_groq.chat.completions.create.call_count == 1


def test_pre_filter_newsletter_skips_llm(mock_groq):
    with get_conn() as conn:
        msg_id = insert_message(conn, gmail_id="msg3", pre_filter_reason="newsletter_header")

    result = classify_and_store(msg_id)

    assert result is False
    mock_groq.chat.completions.create.assert_not_called()

    with get_conn() as conn:
        clf = conn.execute("SELECT * FROM classifications WHERE message_id = ?", (msg_id,)).fetchone()
    assert clf is not None
    assert clf["model"] == "pre-filter"
    assert clf["is_task"] == 0


def test_pre_filter_automated_sender_skips_llm(mock_groq):
    with get_conn() as conn:
        msg_id = insert_message(conn, gmail_id="msg4",
                                sender_email="noreply@github.com",
                                pre_filter_reason="automated_sender")

    classify_and_store(msg_id)
    mock_groq.chat.completions.create.assert_not_called()
