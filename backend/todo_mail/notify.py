"""Cross-platform desktop notifications.

Tries the best mechanism for each OS in this order:

  macOS:   pync (NSUserNotification, supports click → open URL)
           → osascript fallback (no click handler)
  Linux:   plyer → notify-send (no click handler)
  Windows: plyer → win10toast (no click handler)

If nothing works, logs a warning and silently no-ops. The `url` argument
is honored only on macOS via pync; on Linux and Windows the notification
shows the text but doesn't open the URL on click — that's a platform
limitation we intentionally accept rather than ship a flaky polyfill.
"""

import logging
import platform
import shutil
import subprocess

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()  # 'Darwin' | 'Linux' | 'Windows'


def _notify_macos(title: str, message: str, url: str | None) -> bool:
    try:
        import pync  # type: ignore[import-not-found]
        pync.notify(message, title=title, open=url or "")
        return True
    except Exception:
        pass

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True, check=False)
        return True
    except Exception:
        return False


def _notify_plyer(title: str, message: str) -> bool:
    try:
        from plyer import notification  # type: ignore[import-not-found]
        notification.notify(title=title, message=message, app_name="InboxPilot", timeout=10)
        return True
    except Exception:
        return False


def _notify_linux_fallback(title: str, message: str) -> bool:
    if not shutil.which("notify-send"):
        return False
    try:
        subprocess.run(
            ["notify-send", "--app-name=InboxPilot", title, message],
            timeout=5, capture_output=True, check=False,
        )
        return True
    except Exception:
        return False


def send_notification(title: str, message: str, url: str | None = None) -> None:
    """Send a desktop notification. Best-effort, never raises."""
    ok = False
    if _SYSTEM == "Darwin":
        ok = _notify_macos(title, message, url)
    elif _SYSTEM == "Linux":
        ok = _notify_plyer(title, message) or _notify_linux_fallback(title, message)
    elif _SYSTEM == "Windows":
        ok = _notify_plyer(title, message)

    if not ok:
        logger.warning("Could not send notification: %s — %s", title, message)
