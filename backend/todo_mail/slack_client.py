import logging
import time

import requests

from .settings import delete_secret, get_secret, set_secret

logger = logging.getLogger(__name__)

_KEYCHAIN_KEY = "slack-oauth"
_BASE = "https://slack.com/api"


def load_slack_token() -> str | None:
    return get_secret(_KEYCHAIN_KEY)


def save_slack_token(token: str) -> None:
    set_secret(_KEYCHAIN_KEY, token.strip())


def delete_slack_token() -> None:
    delete_secret(_KEYCHAIN_KEY)


class SlackClient:
    def __init__(self, token: str):
        self._token = token
        self._user_cache: dict[str, str] = {}
        self._avatar_cache: dict[str, str | None] = {}
        self._email_cache: dict[str, str | None] = {}
        self._thread_parent_cache: dict[str, dict | None] = {}

    def _get(self, method: str, **params) -> dict:
        for attempt in range(3):
            r = requests.get(
                f"{_BASE}/{method}",
                headers={"Authorization": f"Bearer {self._token}"},
                params=params,
                timeout=30,
            )
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "1"))
                logger.warning("Slack rate limit on %s — waiting %ds", method, retry_after)
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error in {method}: {data.get('error', 'unknown')}")
            return data
        raise RuntimeError(f"Slack API rate limit exceeded for {method} after 3 retries")

    def test_auth(self) -> dict:
        """Returns team_id, user_id, team, user fields."""
        return self._get("auth.test")

    def get_team_id(self) -> str:
        return self.test_auth()["team_id"]

    def test_is_dm_supported(self) -> bool:
        """Probe whether search.messages supports the is:dm modifier."""
        try:
            data = self._get("search.messages", query="is:dm", count=1)
            return data.get("ok", False)
        except Exception:
            return False

    def _search_messages(self, query: str, oldest_ts: str | None) -> list[dict]:
        """Run a paginated search.messages query with optional date cutoff."""
        from datetime import datetime, timedelta, timezone

        q = query
        if oldest_ts:
            try:
                dt = datetime.fromtimestamp(float(oldest_ts), tz=timezone.utc)
                after_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
                q += f" after:{after_date}"
            except (ValueError, TypeError):
                pass

        matches: list[dict] = []
        page = 1
        while True:
            try:
                data = self._get(
                    "search.messages",
                    query=q,
                    count=100,
                    sort="timestamp",
                    sort_dir="asc",
                    page=page,
                )
            except RuntimeError as exc:
                if "missing_scope" in str(exc):
                    logger.warning("search:read scope missing — query '%s' skipped", query)
                else:
                    logger.warning("search.messages error for '%s': %s", query, exc)
                break
            msgs = data.get("messages", {})
            matches.extend(msgs.get("matches", []))
            paging = msgs.get("paging", {})
            if page >= paging.get("pages", 1):
                break
            page += 1

        return matches

    def search_dm_messages(self, oldest_ts: str | None = None) -> list[dict]:
        """Search all DM messages (incoming and outgoing) using is:dm modifier."""
        return self._search_messages("is:dm", oldest_ts)

    def search_outgoing_messages(self, user_id: str, oldest_ts: str | None = None) -> list[dict]:
        """Search messages sent by user_id (fallback when is:dm unsupported)."""
        return self._search_messages(f"from:<@{user_id}>", oldest_ts)

    def search_messages_by_sender(self, sender_user_id: str, oldest_ts: str | None = None) -> list[dict]:
        """Search messages from a specific sender."""
        return self._search_messages(f"from:<@{sender_user_id}>", oldest_ts)

    def search_mentions(self, user_id: str, oldest_ts: str | None = None) -> list[dict]:
        """Return channel messages that @-mention user_id, oldest-first."""
        return self._search_messages(f"<@{user_id}>", oldest_ts)

    def prefetch_users(self, user_ids: list[str]) -> None:
        """Resolve multiple user IDs in parallel to warm the in-process cache."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        unknown = [uid for uid in set(user_ids) if uid and uid not in self._user_cache]
        if not unknown:
            return
        with ThreadPoolExecutor(max_workers=min(10, len(unknown))) as pool:
            for f in as_completed({pool.submit(self.resolve_user_info, uid) for uid in unknown}):
                try:
                    f.result()
                except Exception:
                    pass

    def list_dm_conversations(self) -> list[dict]:
        """Return all im (1:1 DM) and mpim (group DM) conversations the token can see."""
        channels: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {"types": "im,mpim", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = self._get("conversations.list", **params)
            channels.extend(data.get("channels", []))
            cursor = data.get("response_metadata", {}).get("next_cursor") or None
            if not cursor:
                break
        # Defensive filter: Slack sometimes returns public channels with is_mpim=true.
        # Real DMs/group DMs do not have is_channel=true.
        return [
            c for c in channels
            if (c.get("is_im") or c.get("is_mpim")) and not c.get("is_channel")
        ]

    def fetch_history(self, channel_id: str, oldest: str | None = None) -> list[dict]:
        """Fetch messages from a DM channel (newest-first). Returns [] on access error."""
        params: dict = {"channel": channel_id, "limit": 100}
        if oldest:
            params["oldest"] = oldest
        try:
            data = self._get("conversations.history", **params)
            return data.get("messages", [])
        except RuntimeError as exc:
            err = str(exc)
            if any(e in err for e in ("channel_not_found", "not_in_channel", "missing_scope")):
                logger.warning("Cannot read channel %s: %s", channel_id, exc)
                return []
            raise

    def get_thread_parent(self, channel_id: str, thread_ts: str) -> dict | None:
        """Return the root message of a thread, cached. Returns None on failure."""
        cache_key = f"{channel_id}:{thread_ts}"
        if cache_key in self._thread_parent_cache:
            return self._thread_parent_cache[cache_key]
        try:
            data = self._get(
                "conversations.replies",
                channel=channel_id,
                ts=thread_ts,
                limit=1,
                inclusive=True,
            )
            msgs = data.get("messages", [])
            result = msgs[0] if msgs else None
        except Exception as exc:
            logger.warning("Cannot fetch thread parent %s/%s: %s", channel_id, thread_ts, exc)
            result = None
        self._thread_parent_cache[cache_key] = result
        return result

    def resolve_user_info(self, user_id: str) -> tuple[str, str | None]:
        """Return (display_name, avatar_url) for a user, cached."""
        if user_id in self._user_cache:
            return self._user_cache[user_id], self._avatar_cache.get(user_id)
        try:
            data = self._get("users.info", user=user_id)
            profile = data["user"].get("profile", {})
            name = (
                profile.get("display_name_normalized")
                or profile.get("display_name")
                or profile.get("real_name_normalized")
                or profile.get("real_name")
                or user_id
            )
            avatar = profile.get("image_72") or profile.get("image_48") or None
            self._user_cache[user_id] = name
            self._avatar_cache[user_id] = avatar
            # email is only present when the token has the users:read.email scope.
            self._email_cache[user_id] = profile.get("email") or None
            return name, avatar
        except Exception:
            return user_id, None

    def resolve_user_email(self, user_id: str) -> str | None:
        """Return the user's email if the token has users:read.email scope, else None.
        Cached alongside resolve_user_info()."""
        if user_id in self._email_cache:
            return self._email_cache[user_id]
        # Trigger a users.info call to populate the email cache.
        self.resolve_user_info(user_id)
        return self._email_cache.get(user_id)

    def resolve_username(self, user_id: str) -> str:
        name, _ = self.resolve_user_info(user_id)
        return name
