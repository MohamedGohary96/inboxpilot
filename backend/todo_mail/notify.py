import logging
import subprocess

logger = logging.getLogger(__name__)


def send_notification(title: str, message: str, url: str | None = None) -> None:
    """Send a macOS desktop notification. Tries pync first, falls back to osascript."""
    try:
        import pync
        pync.notify(message, title=title, open=url or "")
        return
    except Exception:
        pass

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True, check=False)
    except Exception:
        logger.warning("Could not send notification: %s — %s", title, message)
