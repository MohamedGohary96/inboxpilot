import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, calendar, contacts, feedback, metrics, news, poll, priority_senders, settings_api, status, tasks, slack_auth
from .db import init_db

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)


_setup_logging()
logger = logging.getLogger(__name__)
# Packaged install: dist/ is bundled inside the package directory.
# Dev mode fallback: look for the Vite build output at the repo root.
_DIST = Path(__file__).parent / "dist"
if not _DIST.exists():
    _DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from .events import log_event
    log_event("app_started")

    try:
        from .mail import backfill_news_categories
        backfill_news_categories()
    except Exception:
        logger.exception("News backfill failed (non-fatal)")

    from .mail import GmailClient, load_credentials, save_credentials
    from .scheduler import start_scheduler, stop_scheduler, rehydrate_reminders
    from .calendar_client import init_calendar
    from google.auth.transport.requests import Request

    creds = load_credentials()
    if creds:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds)
            except Exception:
                logger.warning("Could not refresh Google token — poll disabled until reauth")
                creds = None

        if creds and not creds.expired:
            gmail = GmailClient(creds)
            app.state.gmail = gmail
            init_calendar(creds)

            from .slack_client import SlackClient, load_slack_token
            slack_client = None
            slack_token = load_slack_token()
            if slack_token:
                try:
                    slack_client = SlackClient(slack_token)
                    slack_client.test_auth()  # validate token
                    app.state.slack = slack_client
                    logger.info("Slack client ready")
                except Exception:
                    logger.warning("Slack token invalid — Slack polling disabled")
                    slack_client = None

            start_scheduler(gmail, slack_client)
            rehydrate_reminders()
            email = gmail.get_account_email()
            if email:
                from .settings import set_setting
                set_setting("account_email", email)
            logger.info("Gmail client ready — %s", email or "unknown account")
    else:
        logger.warning("No Google credentials found — run 'todo-mail start' to authenticate")

    yield

    stop_scheduler()


app = FastAPI(title="todo-mail", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        json.dumps({
            "type": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": ms,
        })
    )
    return response

app.include_router(auth.router, prefix="/api")
app.include_router(slack_auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(poll.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(priority_senders.router, prefix="/api")
app.include_router(news.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # index.html must never be cached — its name is stable but the hashed
        # asset URLs it references change on every build. If a stale HTML is
        # served, the browser keeps pointing at deleted asset files.
        return FileResponse(
            str(_DIST / "index.html"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
else:
    from fastapi.responses import HTMLResponse

    @app.get("/", include_in_schema=False)
    def dev_placeholder():
        return HTMLResponse("""
<!doctype html><html><head><title>todo-mail</title>
<style>body{font-family:monospace;padding:2rem;}</style></head>
<body>
<h2>todo-mail — backend running</h2>
<p>Frontend not built yet. Run <code>make dev-frontend</code> in a second terminal.</p>
<p>API: <a href="/api/health">/api/health</a> &nbsp;|&nbsp; <a href="/docs">/docs</a></p>
</body></html>
""")
