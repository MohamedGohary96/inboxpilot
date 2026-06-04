import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class SlackTokenBody(BaseModel):
    token: str


_REQUIRED_SCOPES = ["im:history", "im:read", "mpim:history", "mpim:read", "users:read", "users:read.email", "search:read"]


@router.post("/auth/slack/connect")
def slack_connect(body: SlackTokenBody, request: Request):
    """Store a Slack user token and validate it."""
    from fastapi import HTTPException
    from ..slack_client import SlackClient, save_slack_token

    token = body.token.strip()
    if not token:
        raise HTTPException(400, "token is required")

    if token.startswith("xapp-"):
        raise HTTPException(
            400,
            "App-level tokens (xapp-…) cannot access DMs. "
            "You need a User OAuth Token (xoxp-…). "
            "In your Slack app go to OAuth & Permissions → User Token Scopes, "
            f"add: {', '.join(_REQUIRED_SCOPES)}, then install the app.",
        )

    client = SlackClient(token)
    try:
        info = client.test_auth()
    except Exception as exc:
        raise HTTPException(400, f"Token rejected by Slack: {exc}")

    # Verify the token actually has DM read access by probing conversations.list.
    # auth.test succeeds for any valid token — this catches missing_scope early.
    try:
        client._get("conversations.list", types="im", limit=1)
    except RuntimeError as exc:
        err = str(exc)
        if "missing_scope" in err:
            raise HTTPException(
                400,
                f"Token is valid but missing required scopes. "
                f"In your Slack app go to OAuth & Permissions → User Token Scopes "
                f"and add: {', '.join(_REQUIRED_SCOPES)}. "
                f"Then reinstall the app to your workspace to refresh the token.",
            )
        raise HTTPException(400, f"Slack API error: {exc}")

    save_slack_token(token)

    # Hot-swap the Slack client on the running app
    request.app.state.slack = client

    # Restart scheduler with Slack enabled if Gmail is available
    if hasattr(request.app.state, "gmail"):
        try:
            from ..scheduler import stop_scheduler, start_scheduler, rehydrate_reminders
            stop_scheduler()
            start_scheduler(request.app.state.gmail, client)
            rehydrate_reminders()
        except Exception:
            logger.exception("Could not restart scheduler after Slack connect")

    return {
        "ok": True,
        "team": info.get("team"),
        "user": info.get("user"),
        "team_id": info.get("team_id"),
    }


@router.post("/auth/slack/logout")
def slack_logout(request: Request):
    """Remove Slack credentials and stop Slack polling."""
    from ..slack_client import delete_slack_token
    from ..settings import delete_setting

    delete_slack_token()
    delete_setting("slack_last_poll_at")
    delete_setting("slack_team_id")
    delete_setting("slack_user_id")

    if hasattr(request.app.state, "slack"):
        del request.app.state.slack

    # Restart scheduler without Slack
    if hasattr(request.app.state, "gmail"):
        try:
            from ..scheduler import stop_scheduler, start_scheduler, rehydrate_reminders
            stop_scheduler()
            start_scheduler(request.app.state.gmail)
            rehydrate_reminders()
        except Exception:
            logger.exception("Could not restart scheduler after Slack logout")

    return {"ok": True}


@router.post("/auth/slack/reset")
def slack_reset():
    """Delete all stored Slack messages and tasks, and reset the poll cursor."""
    from ..db import get_conn
    from ..settings import delete_setting

    with get_conn() as conn:
        # Delete tasks whose linked message is a Slack message
        conn.execute(
            "DELETE FROM tasks WHERE source = 'slack'"
        )
        # Delete classifications for Slack messages
        conn.execute(
            "DELETE FROM classifications WHERE message_id IN "
            "(SELECT id FROM messages WHERE source = 'slack')"
        )
        # Delete the Slack messages themselves
        conn.execute("DELETE FROM messages WHERE source = 'slack'")

    delete_setting("slack_last_poll_at")
    return {"ok": True}


@router.post("/auth/slack/poll")
async def slack_poll_now(request: Request):
    """Manually trigger a Slack-only poll (fire-and-forget, uses shared lock)."""
    from fastapi import BackgroundTasks, HTTPException
    from ..poll_progress import (
        try_acquire as progress_acquire,
        release as progress_release,
        reset as progress_reset,
        complete as progress_complete,
    )
    if not hasattr(request.app.state, "slack"):
        raise HTTPException(400, "Slack not connected")
    if not progress_acquire():
        raise HTTPException(409, "Poll already in progress")

    progress_reset()

    async def _run():
        import asyncio
        from ..slack import poll_slack
        try:
            await asyncio.to_thread(poll_slack, request.app.state.slack)
        except Exception:
            logger.exception("Slack poll failed")
        finally:
            progress_complete()
            progress_release()

    import asyncio
    asyncio.ensure_future(_run())
    return {"started": True}
