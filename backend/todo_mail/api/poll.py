import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..poll_progress import (
    reset as progress_reset,
    complete as progress_complete,
    get as progress_get,
    try_acquire as progress_acquire,
    release as progress_release,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/poll/progress")
def get_progress():
    return progress_get()


async def _run_poll(gmail_client, slack_client) -> None:
    """Background task: run Gmail + Slack poll, then release the lock."""
    from ..mail import poll_inbox, mark_needs_reauth, clear_needs_reauth
    from google.auth.exceptions import RefreshError
    try:
        await asyncio.to_thread(poll_inbox, gmail_client)
        clear_needs_reauth()
    except RefreshError as exc:
        logger.warning("Gmail token revoked/expired — flagging reauth needed: %s", exc)
        mark_needs_reauth()
    except Exception:
        logger.exception("Gmail poll failed")
    try:
        if slack_client is not None:
            from ..slack import poll_slack
            await asyncio.to_thread(poll_slack, slack_client)
    except Exception:
        logger.exception("Slack poll failed")
    finally:
        progress_complete()
        progress_release()


@router.post("/poll")
async def trigger_poll(request: Request, background_tasks: BackgroundTasks):
    if not hasattr(request.app.state, "gmail"):
        raise HTTPException(503, "Gmail not authenticated — run 'todo-mail start' to complete OAuth")

    if not progress_acquire():
        raise HTTPException(409, "Poll already in progress")

    progress_reset()
    slack_client = getattr(request.app.state, "slack", None)
    background_tasks.add_task(_run_poll, request.app.state.gmail, slack_client)
    return {"started": True}
