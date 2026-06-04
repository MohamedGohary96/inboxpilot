import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "todo-mail" / "todo.db"


def _ensure_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _migrate_db(conn) -> None:
    """Add columns introduced after the initial schema without wiping existing data."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    additions = {
        "list_unsubscribe":  "TEXT",
        "to_header":         "TEXT",
        "pre_filter_reason": "TEXT",
        "fetch_failures":    "INTEGER DEFAULT 0",
        "source":               "TEXT DEFAULT 'gmail'",
        "slack_channel_id":     "TEXT",
        "slack_ts":             "TEXT",
        "slack_thread_ts":      "TEXT",
        "slack_team_id":        "TEXT",
        "sender_avatar":        "TEXT",
        "slack_sender_user_id": "TEXT",
        "slack_sender_email":   "TEXT",
        "news_category":        "TEXT",
        "news_repo":            "TEXT",
        "news_summary":         "TEXT",
        "news_dismissed":       "INTEGER DEFAULT 0",
    }
    for col, typedef in additions.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {typedef}")
    _migrate_tasks_v2(conn)
    _migrate_tasks_v3(conn)
    _migrate_tasks_v4(conn)
    _migrate_priority_senders(conn)


def _migrate_tasks_v2(conn) -> None:
    """Recreate tasks table to support manual todos (nullable message_id + source/title/notes)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "source" in cols:
        _migrate_tasks_v3(conn)
        return
    conn.executescript("""
        ALTER TABLE tasks RENAME TO _tasks_bak;

        CREATE TABLE tasks (
            id                  INTEGER PRIMARY KEY,
            message_id          INTEGER UNIQUE REFERENCES messages(id),
            source              TEXT    NOT NULL DEFAULT 'mail',
            title               TEXT,
            notes               TEXT,
            summary             TEXT,
            asker               TEXT,
            extracted_deadline  DATETIME,
            priority            TEXT     DEFAULT 'normal',
            completion          TEXT     DEFAULT 'not_started',
            reply_by            DATETIME,
            status              TEXT     DEFAULT 'open',
            calendar_event_id   TEXT,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO tasks
            (id, message_id, source, title, notes, summary, asker,
             extracted_deadline, priority, reply_by, status, calendar_event_id,
             created_at, updated_at)
        SELECT
            id, message_id, 'mail', NULL, NULL, summary, asker,
            extracted_deadline, priority, reply_by, status, calendar_event_id,
            created_at, updated_at
        FROM _tasks_bak;

        DROP TABLE _tasks_bak;

        CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_reply_by   ON tasks(reply_by);
        CREATE INDEX IF NOT EXISTS idx_tasks_source     ON tasks(source);
        CREATE INDEX IF NOT EXISTS idx_tasks_completion ON tasks(completion);
    """)


def _migrate_tasks_v3(conn) -> None:
    """Add completion column to existing v2 tasks table."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "completion" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN completion TEXT DEFAULT 'not_started'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_completion ON tasks(completion)")


def _migrate_tasks_v4(conn) -> None:
    """Add task_links table for first-class link attachments on tasks."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS task_links (
            id          INTEGER PRIMARY KEY,
            task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            url         TEXT    NOT NULL,
            label       TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_task_links_task_id ON task_links(task_id);
    """)


def _migrate_priority_senders(conn) -> None:
    """Add priority_senders table — VIPs whose tasks force priority=high with a per-VIP reply window."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS priority_senders (
            id                  INTEGER PRIMARY KEY,
            email               TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            note                TEXT,
            reply_window_hours  INTEGER NOT NULL DEFAULT 4,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_priority_senders_email ON priority_senders(email);
    """)


def init_db() -> None:
    _ensure_dir()
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id               INTEGER PRIMARY KEY,
                gmail_message_id TEXT    UNIQUE NOT NULL,
                thread_id        TEXT,
                sender           TEXT,
                sender_email     TEXT,
                subject          TEXT,
                received_at      DATETIME,
                snippet          TEXT,
                body_text        TEXT,
                processed_at     DATETIME
            );

            CREATE TABLE IF NOT EXISTS classifications (
                id             INTEGER PRIMARY KEY,
                message_id     INTEGER NOT NULL REFERENCES messages(id),
                model          TEXT    NOT NULL,
                prompt_version TEXT    NOT NULL,
                is_task        BOOLEAN,
                raw_json       TEXT,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id                  INTEGER PRIMARY KEY,
                message_id          INTEGER NOT NULL UNIQUE REFERENCES messages(id),
                summary             TEXT,
                asker               TEXT,
                extracted_deadline  DATETIME,
                priority            TEXT     DEFAULT 'normal',
                completion          TEXT     DEFAULT 'not_started',
                reply_by            DATETIME,
                status              TEXT     DEFAULT 'open',
                calendar_event_id   TEXT,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id         INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES messages(id),
                kind       TEXT    NOT NULL,
                note       TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY,
                kind       TEXT    NOT NULL,
                data       TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS task_links (
                id         INTEGER PRIMARY KEY,
                task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                url        TEXT    NOT NULL,
                label      TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS priority_senders (
                id                  INTEGER PRIMARY KEY,
                email               TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                note                TEXT,
                reply_window_hours  INTEGER NOT NULL DEFAULT 4,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_messages_gmail_id ON messages(gmail_message_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_reply_by    ON tasks(reply_by);
            CREATE INDEX IF NOT EXISTS idx_task_links_task_id ON task_links(task_id);
            CREATE INDEX IF NOT EXISTS idx_priority_senders_email ON priority_senders(email);
            CREATE INDEX IF NOT EXISTS idx_events_kind       ON events(kind);
        """)
        _migrate_db(conn)


@contextmanager
def get_conn():
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
