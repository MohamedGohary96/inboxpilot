import asyncio
import logging
import threading

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()

_reauth_state: str = "idle"  # "idle" | "pending" | "done" | "error"


def get_reauth_state() -> str:
    return _reauth_state


def _run_oauth_flow(app, loop: asyncio.AbstractEventLoop) -> None:
    global _reauth_state
    # AsyncIOScheduler.start() calls asyncio.get_event_loop() — must set it here
    # so the scheduler attaches to the main event loop, not a dead thread loop.
    asyncio.set_event_loop(loop)
    try:
        from ..mail import ensure_authenticated, GmailClient, clear_needs_reauth
        from ..settings import delete_secret, set_setting
        from ..calendar_client import init_calendar
        from ..scheduler import stop_scheduler, start_scheduler, rehydrate_reminders

        # Force fresh OAuth by deleting existing credentials first
        delete_secret("google-oauth")

        creds = ensure_authenticated()
        gmail = GmailClient(creds)

        email = gmail.get_account_email()
        if email:
            set_setting("account_email", email)

        app.state.gmail = gmail
        init_calendar(creds)
        stop_scheduler()
        start_scheduler(gmail)
        rehydrate_reminders()

        from .contacts import clear_photo_cache
        clear_photo_cache()
        clear_needs_reauth()

        _reauth_state = "done"
        logger.info("Reauth complete — authenticated as %s", email)
    except Exception as exc:
        logger.exception("Reauth failed: %s", exc)
        _reauth_state = "error"


@router.post("/auth/reauth")
async def trigger_reauth(request: Request):
    global _reauth_state
    if _reauth_state == "pending":
        return {"state": "pending"}
    _reauth_state = "pending"
    loop = asyncio.get_running_loop()
    t = threading.Thread(target=_run_oauth_flow, args=(request.app, loop), daemon=True)
    t.start()
    return {"state": "pending"}


@router.post("/auth/reauth/reset")
def reset_reauth():
    global _reauth_state
    _reauth_state = "idle"
    return {"state": "idle"}


@router.post("/auth/logout")
def logout(request: Request):
    global _reauth_state
    from ..settings import delete_secret, set_setting
    from ..scheduler import stop_scheduler
    from ..calendar_client import clear_calendar

    delete_secret("google-oauth")
    set_setting("account_email", "")
    stop_scheduler()
    clear_calendar()
    _reauth_state = "idle"

    if hasattr(request.app.state, "gmail"):
        del request.app.state.gmail

    return {"ok": True}
