import logging
import time
from datetime import datetime, timedelta, timezone

from .db import get_conn
from .settings import get_setting, set_setting

logger = logging.getLogger(__name__)


def _slack_msg_id(channel_id: str, ts: str) -> str:
    return f"slack:{channel_id}:{ts}"


def _is_bot_message(msg: dict) -> bool:
    return bool(msg.get("bot_id")) or msg.get("subtype") in (
        "bot_message", "channel_join", "channel_leave", "channel_topic",
        "channel_purpose", "channel_name", "channel_archive", "channel_unarchive",
        "message_deleted",
    )


def _ts_to_dt(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc).isoformat()


def _initial_lookback_cursor() -> str:
    lookback_days = int(get_setting("slack_lookback_days") or "7")
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    return f"{cutoff.timestamp():.6f}"


def _is_dm_supported(client) -> bool:
    """Check (cached) whether search.messages supports the is:dm modifier."""
    cached = get_setting("slack_search_is_dm_supported")
    if cached is not None:
        return cached == "1"
    supported = client.test_is_dm_supported()
    set_setting("slack_search_is_dm_supported", "1" if supported else "0")
    logger.info("Slack search is:dm supported: %s", supported)
    return supported


def _should_run_full_sweep() -> bool:
    """True if 6+ hours have elapsed since the last full channel sweep."""
    last = get_setting("slack_last_full_sweep_at")
    if not last:
        return True
    try:
        return (time.time() - float(last)) > 6 * 3600
    except (ValueError, TypeError):
        return True


def _known_dm_sender_ids() -> list[str]:
    """Return user IDs of known DM senders from stored Slack messages."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT slack_sender_user_id FROM messages"
            " WHERE source = 'slack' AND slack_sender_user_id IS NOT NULL"
            " LIMIT 50"
        ).fetchall()
    return [r[0] for r in rows]


def _dedupe(msgs: list[dict]) -> list[dict]:
    """Remove duplicate search result messages keyed by channel_id:ts."""
    seen: set[str] = set()
    out: list[dict] = []
    for m in msgs:
        ch = m.get("channel", {})
        ch_id = ch.get("id", "") if isinstance(ch, dict) else str(ch)
        key = f"{ch_id}:{m.get('ts', '')}"
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def _is_real_dm(channel: dict | None) -> bool:
    """True when a search-result channel object represents a DM or group DM."""
    if not isinstance(channel, dict):
        return False
    return bool(channel.get("is_im") or channel.get("is_mpim")) and not channel.get("is_channel")


def _enrich_body_with_parent(msg: dict, client, channel_id: str) -> str:
    """Return message text, appending thread parent context when appropriate."""
    body = msg.get("text", "").strip()
    ts = msg.get("ts", "")
    thread_ts = msg.get("thread_ts")
    if thread_ts and thread_ts != ts:
        parent = client.get_thread_parent(channel_id, thread_ts)
        if parent:
            parent_text = parent.get("text", "").strip()
            parent_uid = parent.get("user", "")
            parent_name = client.resolve_username(parent_uid) if parent_uid else "Unknown"
            if parent_text:
                body = f"{body}\n\n[Replying to {parent_name}: {parent_text}]"
    return body


def _store_msg(
    slack_id: str, channel_id: str, ts: str, thread_ts: str | None,
    sender_name: str, sender_avatar: str | None, msg_user_id: str | None,
    subject: str, body: str, received_at: str, team_id: str,
    sender_email: str | None = None,
) -> "sqlite3.Row | None":
    """INSERT OR IGNORE a message row, returning the id row if it was inserted."""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (gmail_message_id, thread_id, sender, sender_email, subject,
                received_at, snippet, body_text, processed_at,
                source, slack_channel_id, slack_ts, slack_thread_ts, slack_team_id,
                sender_avatar, slack_sender_user_id, slack_sender_email)
               VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'slack', ?, ?, ?, ?, ?, ?, ?)""",
            (
                slack_id,
                thread_ts or ts,
                sender_name,
                subject,
                received_at,
                body[:200],
                body,
                datetime.now(tz=timezone.utc).isoformat(),
                channel_id,
                ts,
                thread_ts,
                team_id,
                sender_avatar,
                msg_user_id or None,
                sender_email,
            ),
        )
        return conn.execute(
            "SELECT id FROM messages WHERE gmail_message_id = ?", (slack_id,)
        ).fetchone()


def _classify_row(msg_row, slack_id: str) -> None:
    from .classify import classify_and_store
    try:
        classify_and_store(msg_row["id"])
    except Exception:
        logger.exception("Failed to classify Slack message %s", slack_id)


def _process_search_result(msg: dict, client, user_id: str, team_id: str) -> bool:
    """Store and classify a single search.messages result. Returns True if newly stored."""
    ts = msg.get("ts", "")
    if not ts or _is_bot_message(msg):
        return False

    channel = msg.get("channel", {})
    channel_id = channel.get("id", "") if isinstance(channel, dict) else str(channel)
    if not channel_id:
        return False

    slack_id = _slack_msg_id(channel_id, ts)

    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM messages WHERE gmail_message_id = ?", (slack_id,)
        ).fetchone():
            return False

    msg_user_id = msg.get("user", "")
    sender_email = None
    if msg_user_id:
        sender_name, sender_avatar = client.resolve_user_info(msg_user_id)
        sender_email = client.resolve_user_email(msg_user_id)
    else:
        sender_name = msg.get("username") or "Unknown"
        sender_avatar = None

    body = msg.get("text", "").strip()
    received_at = _ts_to_dt(ts)
    thread_ts = msg.get("thread_ts")
    is_outgoing = msg_user_id == user_id

    is_im = isinstance(channel, dict) and channel.get("is_im", False)
    is_mpim = isinstance(channel, dict) and channel.get("is_mpim", False)
    channel_name = channel.get("name", "") if isinstance(channel, dict) else ""
    if is_im or is_mpim:
        subject = "DM you sent" if is_outgoing else f"DM from {sender_name}"
    else:
        subject = f"Mentioned in #{channel_name}" if channel_name else "Channel mention"

    msg_row = _store_msg(
        slack_id, channel_id, ts, thread_ts,
        sender_name, sender_avatar, msg_user_id or None,
        subject, body, received_at, team_id,
        sender_email=sender_email,
    )
    if msg_row:
        _classify_row(msg_row, slack_id)
        return True
    return False


def poll_slack(client) -> int:
    """Fetch new DM messages and channel mentions, store and classify. Returns new message count."""
    from .poll_progress import update as progress

    oldest_ts = get_setting("slack_last_poll_at") or _initial_lookback_cursor()
    team_id = _get_or_cache_team_id(client)
    user_id = _get_or_cache_user_id(client)

    new_count = 0
    latest_ts = oldest_ts

    # Phase 1: Search-based DM fetch (fast — a few API calls)
    progress("Searching Slack DMs…")
    is_dm_ok = _is_dm_supported(client)

    if is_dm_ok:
        logger.info("Slack DM strategy: is:dm search")
        dm_msgs = client.search_dm_messages(oldest_ts)
    else:
        logger.info("Slack DM strategy: fallback per-sender search")
        dm_msgs = client.search_outgoing_messages(user_id, oldest_ts)
        for sender_id in _known_dm_sender_ids():
            dm_msgs.extend(client.search_messages_by_sender(sender_id, oldest_ts))
        dm_msgs = _dedupe(dm_msgs)

    logger.info("DM search returned %d candidate(s)", len(dm_msgs))

    unique_uids = [uid for uid in {m.get("user", "") for m in dm_msgs} if uid]
    if unique_uids:
        client.prefetch_users(unique_uids)

    for msg in dm_msgs:
        ts = msg.get("ts", "")
        if not ts or ts <= oldest_ts:
            continue

        channel = msg.get("channel", {})

        # In fallback mode, skip non-DM channels
        if not is_dm_ok and not _is_real_dm(channel if isinstance(channel, dict) else None):
            is_private = channel.get("is_private") if isinstance(channel, dict) else None
            if is_private is not None and not is_private:
                continue  # public channel in fallback — skip

        if _process_search_result(msg, client, user_id, team_id):
            new_count += 1
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

    # Phase 2: Channel @-mentions
    progress("Scanning channel mentions…")
    mention_count, mention_latest = _poll_mentions(client, user_id, oldest_ts, team_id)
    new_count += mention_count
    if mention_latest and (latest_ts is None or mention_latest > latest_ts):
        latest_ts = mention_latest

    # Phase 3: Periodic full sweep — only needed when is:dm search is unavailable.
    # When is:dm works, search already covers all DMs so the sweep is redundant.
    if _should_run_full_sweep():
        if is_dm_ok:
            # is:dm search already covered everything — just advance the timestamp
            logger.info("Full sweep skipped (is:dm search active)")
            set_setting("slack_last_full_sweep_at", str(int(time.time())))
        else:
            progress("Full Slack channel sweep…")
            sweep_count = _full_channel_sweep(client, user_id, team_id, oldest_ts)
            new_count += sweep_count
            set_setting("slack_last_full_sweep_at", str(int(time.time())))
            logger.info("Full sweep found %d additional message(s)", sweep_count)

    if latest_ts and latest_ts != oldest_ts:
        set_setting("slack_last_poll_at", latest_ts)

    # Safety net: retry classification for any Slack messages without a
    # classifications row. Without this, a transient classifier error (LLM
    # outage, downstream bug) leaves the message stuck — the dedupe check at
    # the top of _process_search_result would skip it on every future poll.
    from .classify import classify_and_store
    with get_conn() as conn:
        unclassified = conn.execute(
            "SELECT id FROM messages"
            " WHERE source = 'slack'"
            "   AND id NOT IN (SELECT message_id FROM classifications)"
            " ORDER BY received_at DESC LIMIT 50"
        ).fetchall()
    if unclassified:
        logger.info("Retrying classification for %d unclassified Slack message(s)", len(unclassified))
    for row in unclassified:
        try:
            classify_and_store(row["id"])
        except Exception:
            logger.exception("Failed to classify Slack message %d", row["id"])

    logger.info("Slack poll complete — %d new message(s)", new_count)
    return new_count


def _full_channel_sweep(client, user_id: str, team_id: str, oldest_ts: str) -> int:
    """Per-channel history sweep — catches messages that search may miss. Returns new count."""
    from .poll_progress import update as progress

    all_conversations = client.list_dm_conversations()
    logger.info("Full sweep: checking %d DM channels", len(all_conversations))

    new_count = 0

    for i, ch in enumerate(all_conversations):
        progress("Full Slack channel sweep", i, len(all_conversations))
        time.sleep(0.5)  # stay well under Slack's Tier 3 limit (50 req/min)
        channel_id = ch["id"]
        messages = client.fetch_history(channel_id, oldest=oldest_ts)

        for msg in reversed(messages):
            if _is_bot_message(msg):
                continue

            ts = msg.get("ts", "")
            if not ts:
                continue

            slack_id = _slack_msg_id(channel_id, ts)

            with get_conn() as conn:
                if conn.execute(
                    "SELECT 1 FROM messages WHERE gmail_message_id = ?", (slack_id,)
                ).fetchone():
                    continue

            msg_user_id = msg.get("user", "")
            sender_email = None
            if msg_user_id:
                sender_name, sender_avatar = client.resolve_user_info(msg_user_id)
                sender_email = client.resolve_user_email(msg_user_id)
            else:
                sender_name, sender_avatar = "Unknown", None

            body = _enrich_body_with_parent(msg, client, channel_id)
            received_at = _ts_to_dt(ts)
            thread_ts = msg.get("thread_ts")
            is_outgoing = msg_user_id == user_id
            subject = "DM you sent" if is_outgoing else f"DM from {sender_name}"

            msg_row = _store_msg(
                slack_id, channel_id, ts, thread_ts,
                sender_name, sender_avatar, msg_user_id or None,
                subject, body, received_at, team_id, sender_email=sender_email,
            )
            if msg_row:
                new_count += 1
                _classify_row(msg_row, slack_id)

    return new_count


def _poll_mentions(client, user_id: str, oldest_ts: str | None, team_id: str) -> tuple[int, str | None]:
    """Poll channel @-mentions via search.messages. Returns (count, latest_ts)."""
    matches = client.search_mentions(user_id, oldest_ts)
    new_count = 0
    latest_ts: str | None = None

    for match in matches:
        ts = match.get("ts", "")
        if not ts:
            continue

        # Skip messages older than or equal to last poll (search after: is date-level only)
        if oldest_ts and ts <= oldest_ts:
            continue

        channel = match.get("channel", {})
        channel_id = channel.get("id", "")
        channel_name = channel.get("name", "")
        if not channel_id:
            continue

        # Skip public channels — only keep DMs, group DMs, and private channels
        if channel.get("is_private") is False:
            continue

        slack_id = _slack_msg_id(channel_id, ts)

        with get_conn() as conn:
            if conn.execute(
                "SELECT 1 FROM messages WHERE gmail_message_id = ?", (slack_id,)
            ).fetchone():
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
                continue

        user = match.get("user", "")
        sender_email = None
        if user:
            sender_name, sender_avatar = client.resolve_user_info(user)
            sender_email = client.resolve_user_email(user)
        else:
            sender_name = match.get("username") or "Unknown"
            sender_avatar = None

        body = _enrich_body_with_parent(match, client, channel_id)
        received_at = _ts_to_dt(ts)
        thread_ts = match.get("thread_ts")
        subject = f"Mentioned in #{channel_name}" if channel_name else "Channel mention"

        msg_row = _store_msg(
            slack_id, channel_id, ts, thread_ts,
            sender_name, sender_avatar, user or None,
            subject, body, received_at, team_id, sender_email=sender_email,
        )
        if msg_row:
            new_count += 1
            _classify_row(msg_row, slack_id)

        if latest_ts is None or ts > latest_ts:
            latest_ts = ts

    return new_count, latest_ts


def _get_or_cache_team_id(client) -> str:
    team_id = get_setting("slack_team_id")
    if not team_id:
        try:
            team_id = client.get_team_id()
            set_setting("slack_team_id", team_id)
        except Exception:
            logger.warning("Could not fetch Slack team ID")
            team_id = "unknown"
    return team_id


def _get_or_cache_user_id(client) -> str:
    user_id = get_setting("slack_user_id")
    if not user_id:
        try:
            info = client.test_auth()
            user_id = info["user_id"]
            set_setting("slack_user_id", user_id)
        except Exception:
            logger.warning("Could not fetch Slack user ID")
            user_id = ""
    return user_id
