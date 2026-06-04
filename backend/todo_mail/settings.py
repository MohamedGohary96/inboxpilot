import keyring
import keyring.errors
from .db import get_conn

_SERVICE = "todo-mail"

DEFAULTS: dict[str, str] = {
    "reply_by_days": "2",
    "reply_by_hour": "17",
    "poll_interval_minutes": "5",
    "reminder_offsets_hours": "24,1,0",
    "gmail_query": "in:inbox is:unread -category:promotions -category:social newer_than:7d",
    "slack_lookback_days": "7",
    "user_name": "",
}


def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return DEFAULTS.get(key)


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_secret(name: str) -> str | None:
    return keyring.get_password(_SERVICE, name)


def set_secret(name: str, value: str) -> None:
    keyring.set_password(_SERVICE, name, value)


def delete_setting(key: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(_SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
