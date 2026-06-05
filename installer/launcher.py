"""
InboxPilot launcher — entry point for the PyInstaller bundle.

Starts the FastAPI/uvicorn server then opens the app in the default browser.
All paths are resolved relative to the bundle so the frozen app works from
any location on disk.
"""
import multiprocessing
import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

# ── PyInstaller path fix ──────────────────────────────────────────────────────
# When frozen, sys._MEIPASS is the temp folder where PyInstaller extracts files.
# We add it to sys.path so all bundled packages are importable.
if getattr(sys, 'frozen', False):
    bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    sys.path.insert(0, str(bundle_dir))
    # Point the backend at the bundled frontend dist
    os.environ.setdefault('INBOXPILOT_DIST', str(bundle_dir / 'todo_mail_dist'))
else:
    bundle_dir = Path(__file__).parent

PORT = 8765
HOST = '127.0.0.1'
URL  = f'http://{HOST}:{PORT}'


def _open_browser():
    """Wait until the server is accepting connections, then open the browser."""
    import urllib.request
    for _ in range(40):          # up to 20 s
        try:
            urllib.request.urlopen(f'{URL}/api/health', timeout=1)
            webbrowser.open(URL)
            return
        except Exception:
            time.sleep(0.5)


def main():
    # multiprocessing.freeze_support() must be called first on Windows
    multiprocessing.freeze_support()

    # Initialise the database before starting the server
    from todo_mail.db import init_db
    init_db()

    # Authenticate with Google (shows browser window if needed)
    from todo_mail.mail import ensure_authenticated
    try:
        ensure_authenticated()
    except SystemExit:
        pass  # user cancelled — server will still start, wizard will handle it

    # Open browser once server is ready
    threading.Thread(target=_open_browser, daemon=True).start()

    # Start uvicorn
    import uvicorn
    uvicorn.run(
        'todo_mail.app:app',
        host=HOST,
        port=PORT,
        reload=False,
        log_level='warning',
    )


if __name__ == '__main__':
    main()
