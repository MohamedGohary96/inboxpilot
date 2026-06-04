import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .settings import get_setting

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


# ── poll jobs ─────────────────────────────────────────────────────────────────

async def _poll_job(client) -> None:
    from .mail import poll_inbox, mark_needs_reauth, clear_needs_reauth
    from .poll_progress import try_acquire, release, reset, complete
    from google.auth.exceptions import RefreshError
    if not try_acquire():
        logger.debug("Scheduler skipping Gmail poll — another poll is already running")
        return
    reset()
    try:
        await asyncio.to_thread(poll_inbox, client)
        clear_needs_reauth()
    except RefreshError as exc:
        logger.warning("Gmail token revoked/expired — flagging reauth needed: %s", exc)
        mark_needs_reauth()
    finally:
        complete()
        release()


async def _slack_poll_job(client) -> None:
    from .slack import poll_slack
    from .poll_progress import try_acquire, release, reset, complete
    if not try_acquire():
        logger.debug("Scheduler skipping Slack poll — another poll is already running")
        return
    reset()
    try:
        await asyncio.to_thread(poll_slack, client)
    finally:
        complete()
        release()


# ── reminder jobs ─────────────────────────────────────────────────────────────

def _fire_reminder(task_id: int, hours_before: int) -> None:
    from .db import get_conn
    from .notify import send_notification

    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.reply_by, t.status, m.subject, m.sender, m.thread_id
               FROM tasks t JOIN messages m ON t.message_id = m.id
               WHERE t.id = ?""",
            (task_id,),
        ).fetchone()

    if not row or row["status"] != "open":
        return

    app_url = f"http://127.0.0.1:8765/?task={task_id}"
    subject = row["subject"] or "(no subject)"
    sender = row["sender"] or "someone"

    if hours_before == 0:
        title = "Overdue reply"
        msg = f"{subject} — from {sender}"
    elif hours_before == 1:
        title = "Reply in 1 hour"
        msg = f"{subject} — from {sender}"
    else:
        title = f"Reply in {hours_before}h"
        msg = f"{subject} — from {sender}"

    send_notification(title, msg, url=app_url)


def _job_id(task_id: int, hours_before: int) -> str:
    return f"reminder_{task_id}_{hours_before}h"


def _reminder_offsets() -> list[int]:
    raw = get_setting("reminder_offsets_hours") or "24,1,0"
    try:
        return [int(x.strip()) for x in raw.split(",")]
    except ValueError:
        return [24, 1, 0]


def schedule_reminders(task_id: int) -> None:
    """Schedule (or replace) reminder jobs for a task based on its current reply_by."""
    if not _scheduler:
        return

    from .db import get_conn

    with get_conn() as conn:
        row = conn.execute(
            "SELECT t.reply_by FROM tasks t WHERE t.id = ? AND t.status = 'open'",
            (task_id,),
        ).fetchone()

    if not row:
        return

    try:
        reply_by = datetime.fromisoformat(row["reply_by"])
    except Exception:
        return

    for hours in _reminder_offsets():
        fire_at = reply_by - timedelta(hours=hours)
        now = datetime.now(tz=fire_at.tzinfo) if fire_at.tzinfo else datetime.now()
        if fire_at <= now:
            continue
        _scheduler.add_job(
            _fire_reminder,
            "date",
            run_date=fire_at,
            args=[task_id, hours],
            id=_job_id(task_id, hours),
            replace_existing=True,
            misfire_grace_time=300,
        )


def cancel_reminders(task_id: int) -> None:
    """Remove all pending reminder jobs for a task."""
    if not _scheduler:
        return
    for hours in _reminder_offsets():
        try:
            _scheduler.remove_job(_job_id(task_id, hours))
        except Exception:
            pass


def rehydrate_reminders() -> None:
    """Re-schedule reminders for all open tasks on app startup."""
    if not _scheduler:
        return

    from .db import get_conn

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM tasks WHERE status = 'open' AND reply_by > datetime('now')"
        ).fetchall()

    for row in rows:
        try:
            schedule_reminders(row["id"])
        except Exception:
            logger.exception("Failed to rehydrate reminder for task %d", row["id"])

    if rows:
        logger.info("Rehydrated reminders for %d open task(s)", len(rows))


# ── lifecycle ─────────────────────────────────────────────────────────────────

def start_scheduler(gmail_client, slack_client=None) -> None:
    global _scheduler
    interval = int(get_setting("poll_interval_minutes") or "5")
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _poll_job,
        "interval",
        minutes=interval,
        args=[gmail_client],
        id="poll_inbox",
        replace_existing=True,
        misfire_grace_time=60,
    )
    if slack_client is not None:
        _scheduler.add_job(
            _slack_poll_job,
            "interval",
            minutes=interval,
            args=[slack_client],
            id="poll_slack",
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("Slack polling enabled — every %d minute(s)", interval)
    _scheduler.start()
    logger.info("Scheduler started — polling every %d minute(s)", interval)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
