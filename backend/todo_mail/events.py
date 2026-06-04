import json
import logging

from .db import get_conn

logger = logging.getLogger(__name__)


def log_event(kind: str, data: dict | None = None) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO events (kind, data) VALUES (?, ?)",
                (kind, json.dumps(data) if data else None),
            )
    except Exception:
        logger.warning("Failed to log event %s", kind)
