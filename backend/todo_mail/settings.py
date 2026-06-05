import logging

import keyring
import keyring.errors
from .db import get_conn

logger = logging.getLogger(__name__)

_SERVICE = "InboxPilot"
_LEGACY_SERVICE = "todo-mail"

# Headless Linux containers (and some desktop installs) ship without a working
# backend like Secret Service or KWallet. Treat that as "no secret stored"
# instead of crashing — callers fall back to environment variables and the
# user can still set the Groq key via the Settings drawer (which writes
# through to `keyring.set_password` and may fail gracefully there too).
_KEYRING_ERRORS = (keyring.errors.KeyringError, RuntimeError, Exception)

DEFAULTS: dict[str, str] = {
    "reply_by_days": "2",
    "reply_by_hour": "17",
    "poll_interval_minutes": "5",
    "reminder_offsets_hours": "24,1,0",
    "gmail_query": "in:inbox is:unread -category:promotions -category:social newer_than:7d",
    "slack_lookback_days": "7",
    "user_name": "",
    "llm_provider": "groq",
    "llm_model": "",
    "llm_base_url": "",
}

_PROVIDER_KEY_NAMES: dict[str, str] = {
    "groq":      "groq-api-key",
    "openai":    "openai-api-key",
    "anthropic": "anthropic-api-key",
}


def set_api_key(provider: str, key: str) -> None:
    """Persist an API key for the given provider in the OS keyring."""
    secret_name = _PROVIDER_KEY_NAMES.get(provider)
    if not secret_name:
        raise ValueError(f"Unknown provider: {provider!r}")
    set_secret(secret_name, key)


def has_api_key(provider: str) -> bool:
    """Return True if a key is stored in the keyring for the given provider."""
    secret_name = _PROVIDER_KEY_NAMES.get(provider)
    if not secret_name:
        return False
    return bool(get_secret(secret_name))


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
    try:
        value = keyring.get_password(_SERVICE, name)
        if value:
            return value
        # Migrate key from the legacy "todo-mail" service on first access
        legacy = keyring.get_password(_LEGACY_SERVICE, name)
        if legacy:
            keyring.set_password(_SERVICE, name, legacy)
            keyring.delete_password(_LEGACY_SERVICE, name)
            return legacy
        return None
    except _KEYRING_ERRORS as exc:
        logger.warning("Keyring read for %r failed (%s) — falling back to env var", name, exc)
        return None


def set_secret(name: str, value: str) -> None:
    try:
        keyring.set_password(_SERVICE, name, value)
    except _KEYRING_ERRORS as exc:
        logger.error("Keyring write for %r failed (%s); install a backend (e.g. python3-secretstorage on Debian/Ubuntu) or set the value via env var", name, exc)
        raise


def delete_setting(key: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(_SERVICE, name)
    except (keyring.errors.PasswordDeleteError, *_KEYRING_ERRORS):
        pass
