import base64
import json
import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import html2text as h2t
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .db import get_conn
from .settings import delete_secret, get_secret, get_setting, set_secret, set_setting

logger = logging.getLogger(__name__)

# Set to True when a Gmail API call fails with invalid_grant (token revoked/expired).
# Surfaced via /api/status so the UI can prompt the user to re-authenticate.
_needs_reauth: bool = False


def needs_reauth() -> bool:
    return _needs_reauth


def mark_needs_reauth() -> None:
    global _needs_reauth
    _needs_reauth = True


def clear_needs_reauth() -> None:
    global _needs_reauth
    _needs_reauth = False


_AUTOMATED_SENDER = re.compile(
    r"noreply|no[-.]reply|donotreply|do[-.]not[-.]reply|"
    r"notifications?@|mailer[-_]daemon|bounce@|postmaster@|"
    r"alerts?@|updates?@|support@.*\.(com|io|co)",
    re.IGNORECASE,
)

# ── GitHub news detection ────────────────────────────────────────────────────
_GITHUB_REPO_PREFIX = re.compile(r"\[([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)\]")
_GITHUB_LIST_ID    = re.compile(r"<([^.]+)\.([^.]+)\.github\.com>")
_GITHUB_RELEASE    = re.compile(r"\b(published a release|release[d]?\b|new release|release notes|v\d+\.\d+)", re.I)
_GITHUB_SECURITY   = re.compile(r"\b(security advisory|vulnerability|cve-|dependabot alert|security alert)", re.I)
_GITHUB_DISCUSSION = re.compile(r"\b(started a discussion|new discussion|discussion #|community discussion)", re.I)
_GITHUB_NEWSLETTER = re.compile(r"\b(github (?:blog|newsletter|update|changelog)|github stars|the github)", re.I)
_GITHUB_PR         = re.compile(r"\(PR\s*#\d+\)|pull request #\d+|review requested", re.I)
_GITHUB_ISSUE      = re.compile(r"\(Issue\s*#\d+\)|issue #\d+", re.I)


def detect_news(sender_email: str | None, subject: str | None, body_text: str | None,
                headers: dict | None = None) -> tuple[str | None, str | None]:
    """Return (category, repo) for GitHub messages, or (None, None) if not GitHub.

    Categories: security, pull_request, issue, release, discussion, newsletter.
    PR/issue notifications may also be tasks — they appear in both places.
    """
    if not sender_email or "@github.com" not in sender_email.lower():
        return None, None

    subj = subject or ""
    body_head = (body_text or "")[:1500]
    headers = headers or {}

    # Order matters: security > PR > issue > release > discussion > newsletter.
    # PR check before release because PR titles often contain "release" / version tags.
    category: str | None = None
    if _GITHUB_SECURITY.search(subj) or _GITHUB_SECURITY.search(body_head):
        category = "security"
    elif _GITHUB_PR.search(subj):
        category = "pull_request"
    elif _GITHUB_ISSUE.search(subj):
        category = "issue"
    elif _GITHUB_RELEASE.search(subj) or "released this" in body_head.lower():
        category = "release"
    elif _GITHUB_DISCUSSION.search(subj) or _GITHUB_DISCUSSION.search(body_head):
        category = "discussion"
    elif _GITHUB_NEWSLETTER.search(subj) or "blog.github.com" in body_head:
        category = "newsletter"

    if not category:
        return None, None

    repo: str | None = None
    m = _GITHUB_REPO_PREFIX.search(subj)
    if m:
        repo = m.group(1)
    else:
        list_id = headers.get("list-id") or headers.get("List-Id") or ""
        m = _GITHUB_LIST_ID.search(list_id)
        if m:
            repo = f"{m.group(2)}/{m.group(1)}"

    return category, repo


def backfill_news_categories() -> int:
    """Re-scan all GitHub messages and (re-)populate news_category/news_repo.
    Idempotent: only writes rows whose category/repo would change."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, sender_email, subject, body_text, news_category, news_repo "
            "FROM messages WHERE LOWER(sender_email) LIKE '%@github.com'"
        ).fetchall()

    updates: list[tuple[str | None, str | None, int]] = []
    for row in rows:
        category, repo = detect_news(row["sender_email"], row["subject"], row["body_text"], {})
        if category != row["news_category"] or repo != row["news_repo"]:
            updates.append((category, repo, row["id"]))

    if updates:
        with get_conn() as conn:
            conn.executemany(
                "UPDATE messages SET news_category = ?, news_repo = ? WHERE id = ?",
                updates,
            )
        logger.info("Backfilled %d GitHub news messages", len(updates))
    return len(updates)

_MAX_FETCH_FAILURES = 3
_MAX_CLASSIFY_BATCH = 50

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
]

_SECRETS_CANDIDATES = [
    Path.home() / ".config" / "todo-mail" / "client_secrets.json",
    Path("client_secrets.json"),
]


def _find_secrets() -> Path | None:
    for p in _SECRETS_CANDIDATES:
        if p.exists():
            return p
    return None


def load_credentials() -> Credentials | None:
    raw = get_secret("google-oauth")
    if not raw:
        return None
    data = json.loads(raw)
    creds = Credentials(
        token=data["token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data.get("scopes", SCOPES),
    )
    if data.get("expiry"):
        creds.expiry = datetime.fromisoformat(data["expiry"])
    return creds


def save_credentials(creds: Credentials) -> None:
    set_secret("google-oauth", json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }))


def ensure_authenticated() -> Credentials:
    """Load credentials from Keychain, refresh if expired, run OAuth flow if absent."""
    creds = load_credentials()

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            logger.warning("Token refresh failed — re-running OAuth flow")
            delete_secret("google-oauth")
            creds = None

    if creds and not creds.expired:
        return creds

    secrets_path = _find_secrets()
    if not secrets_path:
        raise RuntimeError(
            "\n\nNo client_secrets.json found.\n\n"
            "To set up:\n"
            "  1. Go to https://console.cloud.google.com/\n"
            "  2. Create a project, enable Gmail API and Google Calendar API\n"
            "  3. Create OAuth 2.0 credentials  →  type: Desktop app\n"
            "  4. Download the JSON and save it to:\n"
            f"       {_SECRETS_CANDIDATES[0]}\n\n"
            "Then run:  todo-mail start\n"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    save_credentials(creds)
    logger.info("OAuth flow complete — credentials saved to Keychain")
    return creds


# ── Gmail client ──────────────────────────────────────────────────────────────

class GmailClient:
    def __init__(self, creds: Credentials):
        self._creds = creds
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def get_account_email(self) -> str | None:
        try:
            profile = self._svc.users().getProfile(userId="me").execute()
            return profile.get("emailAddress")
        except Exception:
            return None

    def list_new_message_ids(self, query: str, after_date: str | None = None) -> list[str]:
        with get_conn() as conn:
            known: set[str] = {
                row[0] for row in conn.execute("SELECT gmail_message_id FROM messages")
            }

        # Narrow the Gmail search to messages since the last poll so we don't
        # paginate the entire inbox on every run.
        q = query
        if after_date:
            q = f"{q} after:{after_date}".strip()

        ids: list[str] = []
        page_token: str | None = None
        while True:
            kwargs: dict = {"userId": "me", "q": q, "maxResults": 100}
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._svc.users().messages().list(**kwargs).execute()
            for msg in resp.get("messages", []):
                if msg["id"] not in known:
                    ids.append(msg["id"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return ids

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _fetch_raw(self, msg_id: str) -> dict:
        return self._svc.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

    def fetch_and_store(self, msg_id: str) -> None:
        raw = self._fetch_raw(msg_id)

        headers = {
            h["name"].lower(): h["value"]
            for h in raw.get("payload", {}).get("headers", [])
        }

        sender_name, sender_email = _parse_sender(headers.get("from", ""))
        subject = headers.get("subject", "(no subject)")
        date_str = headers.get("date", "")
        list_unsubscribe = headers.get("list-unsubscribe") or headers.get("list_unsubscribe")
        to_header = headers.get("to", "")

        try:
            received_at = parsedate_to_datetime(date_str).isoformat()
        except Exception:
            received_at = datetime.utcnow().isoformat()

        body_text = _strip_quoted(_extract_body(raw.get("payload", {})))
        snippet = raw.get("snippet", "")
        thread_id = raw.get("threadId", "")

        pre_filter_reason: str | None = None
        if list_unsubscribe:
            pre_filter_reason = "newsletter_header"
        elif _AUTOMATED_SENDER.search(sender_email or ""):
            pre_filter_reason = "automated_sender"
        elif _is_calendar_invite(raw.get("payload", {}), subject, body_text):
            pre_filter_reason = "calendar_invite"

        news_category, news_repo = detect_news(sender_email, subject, body_text, headers)

        with get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO messages
                   (gmail_message_id, thread_id, sender, sender_email, subject,
                    received_at, snippet, body_text, processed_at,
                    list_unsubscribe, to_header, pre_filter_reason,
                    news_category, news_repo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)""",
                (msg_id, thread_id, sender_name, sender_email, subject,
                 received_at, snippet, body_text,
                 list_unsubscribe, to_header, pre_filter_reason,
                 news_category, news_repo),
            )


def poll_inbox(client: GmailClient) -> int:
    """Fetch, store, and classify new messages. Returns count of new rows stored."""
    from .classify import classify_and_store
    from .poll_progress import update as progress

    query = get_setting("gmail_query") or ""
    progress("Scanning Gmail inbox…")

    # Build an after: date from the last successful poll so Gmail only returns
    # recent messages instead of paginating the entire inbox every time.
    last_poll = get_setting("last_poll_at")
    after_date: str | None = None
    if last_poll:
        try:
            dt = datetime.fromisoformat(last_poll)
            # Gmail after: accepts YYYY/MM/DD; subtract 1 day as a safety buffer
            after_date = (dt - timedelta(days=1)).strftime("%Y/%m/%d")
        except Exception:
            pass

    new_ids = client.list_new_message_ids(query, after_date)

    # Sequential fetch — googleapiclient uses httplib2 which is NOT thread-safe.
    # Sharing one service across threads corrupts the SSL socket buffer and segfaults
    # in libsystem_malloc. See https://github.com/googleapis/google-api-python-client/blob/main/docs/thread_safety.md
    count = 0
    for i, mid in enumerate(new_ids):
        progress("Fetching Gmail messages", i, len(new_ids))
        try:
            client.fetch_and_store(mid)
            count += 1
        except Exception:
            logger.exception("Failed to fetch message %s after retries — incrementing failure count", mid)
            with get_conn() as conn:
                conn.execute(
                    "UPDATE messages SET fetch_failures = fetch_failures + 1"
                    " WHERE gmail_message_id = ?",
                    (mid,),
                )

    if count:
        logger.info("Stored %d new message(s)", count)

    # Classify messages that:
    # - have no classification yet
    # - were not pre-filtered
    # - have not exceeded the fetch-failure dead-letter threshold
    with get_conn() as conn:
        unclassified = conn.execute(
            "SELECT id FROM messages"
            " WHERE id NOT IN (SELECT message_id FROM classifications)"
            "   AND (pre_filter_reason IS NULL)"
            "   AND (fetch_failures IS NULL OR fetch_failures < ?)"
            " ORDER BY received_at DESC LIMIT ?",
            (_MAX_FETCH_FAILURES, _MAX_CLASSIFY_BATCH),
        ).fetchall()

    for i, row in enumerate(unclassified):
        progress("Classifying Gmail messages", i, len(unclassified))
        try:
            classify_and_store(row["id"])
        except Exception:
            logger.exception("Failed to classify message %d", row["id"])

    set_setting("last_poll_at", datetime.utcnow().isoformat())

    from .events import log_event
    log_event("poll_completed", {"new_messages": count, "classified": len(unclassified)})

    return count


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_sender(raw: str) -> tuple[str, str]:
    m = re.match(r'"?([^"<]*)"?\s*<([^>]+)>', raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    if "@" in raw:
        return raw.strip(), raw.strip()
    return raw.strip(), ""


def _b64decode(data: str) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _b64decode(payload.get("body", {}).get("data", ""))

    if mime_type == "text/html":
        return h2t.html2text(_b64decode(payload.get("body", {}).get("data", "")))

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            return _extract_body(part)
    for part in parts:
        result = _extract_body(part)
        if result.strip():
            return result
    return ""


_QUOTE_PATTERNS = [
    re.compile(r"^On .{10,} wrote:$"),
    re.compile(r"^[-]{3,}.*[Oo]riginal [Mm]essage.*[-]{3,}$"),
    re.compile(r"^From:\s+"),
]

_CALENDAR_SUBJECT_PREFIXES = (
    "invitation:",
    "meeting invite:",
    "you're invited",
    "you have been invited",
    "calendar invite:",
    "new event:",
    "updated event:",
    "cancelled event:",
    "event cancelled:",
    "event updated:",
    "accepted:",
    "tentative:",
    "declined:",
)


def _has_mime_part(payload: dict, mime: str) -> bool:
    if payload.get("mimeType", "").lower() == mime:
        return True
    for part in payload.get("parts", []):
        if _has_mime_part(part, mime):
            return True
    return False


def _has_ics_attachment(payload: dict) -> bool:
    filename = (payload.get("filename") or "").lower()
    if filename.endswith(".ics"):
        return True
    for part in payload.get("parts", []):
        if _has_ics_attachment(part):
            return True
    return False


def _is_calendar_invite(payload: dict, subject: str, body_text: str) -> bool:
    if _has_mime_part(payload, "text/calendar"):
        return True
    if _has_ics_attachment(payload):
        return True
    if "BEGIN:VCALENDAR" in body_text:
        return True
    subj_lower = (subject or "").lower()
    if any(subj_lower.startswith(p) for p in _CALENDAR_SUBJECT_PREFIXES):
        return True
    return False


def _strip_quoted(text: str) -> str:
    lines = text.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if any(p.match(stripped) for p in _QUOTE_PATTERNS):
            break
        clean.append(line)
    return "\n".join(clean).strip()
