from fastapi import APIRouter, Request

from ..db import get_conn
from ..settings import get_setting

router = APIRouter()


@router.get("/status")
def get_status(request: Request):
    authenticated = hasattr(request.app.state, "gmail")

    with get_conn() as conn:
        total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        open_tasks = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'open'"
        ).fetchone()[0]

    last_poll = get_setting("last_poll_at")
    account_email = get_setting("account_email") or None
    slack_connected = hasattr(request.app.state, "slack")

    from .auth import get_reauth_state
    reauth_state = get_reauth_state()

    from ..mail import needs_reauth
    gmail_needs_reauth = needs_reauth()

    from ..classify import has_groq_api_key
    groq_configured = has_groq_api_key()

    from ..mail import _find_secrets
    has_credentials = _find_secrets() is not None

    return {
        "authenticated": authenticated,
        "has_credentials": has_credentials,
        "account_email": account_email,
        "reauth_state": reauth_state,
        "needs_reauth": gmail_needs_reauth,
        "groq_configured": groq_configured,
        "slack_connected": slack_connected,
        "total_messages": total_messages,
        "total_tasks": total_tasks,
        "open_tasks": open_tasks,
        "last_poll": last_poll,
    }
