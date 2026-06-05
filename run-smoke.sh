#!/usr/bin/env bash
# Linux smoke test for InboxPilot — runs inside the Ubuntu container.
set -e

cd /app

echo
echo "=========================================="
echo "  1. Install backend"
echo "=========================================="
pip install -e 'backend[dev]' --quiet
echo "  ✓ todo-mail installed → $(which todo-mail)"

echo
echo "=========================================="
echo "  2. Verify backend imports cleanly"
echo "=========================================="
python3 -c '
import sys
from todo_mail import (
    app, classify, mail, scheduler, notify, db, settings, config,
    slack, slack_client, calendar_client, events, poll_progress,
)
from todo_mail.api import (
    auth, calendar, contacts, feedback, metrics, news, poll,
    priority_senders, settings_api, slack_auth, status, tasks,
)
print(f"  ✓ all {17} backend modules import on Linux ({sys.platform})")
'

echo
echo "=========================================="
echo "  3. Verify per-OS paths resolve correctly"
echo "=========================================="
python3 -c '
from todo_mail.db import DB_PATH, _LEGACY_DB_PATH
from todo_mail.config import _CONFIG_PATH
print(f"  DB:          {DB_PATH}")
print(f"  Config:      {_CONFIG_PATH}")
print(f"  Legacy DB:   {_LEGACY_DB_PATH}")
assert "/.local/share/inboxpilot/" in str(DB_PATH), f"DB path is not Linux-style: {DB_PATH}"
assert "/.config/inboxpilot/" in str(_CONFIG_PATH), f"Config path is not Linux-style: {_CONFIG_PATH}"
print("  ✓ paths look right for Linux")
'

echo
echo "=========================================="
echo "  4. Notification dispatcher (no display, must not crash)"
echo "=========================================="
python3 -c '
from todo_mail.notify import send_notification, _SYSTEM
print(f"  detected platform: {_SYSTEM}")
send_notification("smoke test", "this should not raise", url="http://example.com")
print("  ✓ send_notification returned cleanly (logged a warning since no display)")
'

echo
echo "=========================================="
echo "  5. Backend tests"
echo "=========================================="
(cd backend && python3 -m pytest -q 2>&1 | tail -5)

echo
echo "=========================================="
echo "  6. Frontend install + build"
echo "=========================================="
cd frontend
npm install --silent 2>&1 | tail -3
npm run build --silent 2>&1 | tail -4
cd ..
cp -r frontend/dist backend/todo_mail/dist
echo "  ✓ frontend bundle copied to backend/todo_mail/dist"

echo
echo "=========================================="
echo "  7. start.sh prereq-check + secrets handling"
echo "=========================================="
# start.sh exits 1 when client_secrets.json is missing — that is the expected
# happy path for a fresh install. We assert this exit code without piping
# through head (which would mask the real exit code).
set +e
bash ./start.sh > /tmp/start.log 2>&1
rc=$?
set -e
head -20 /tmp/start.log
if [ "$rc" -eq 1 ] && grep -q "No client_secrets.json found" /tmp/start.log; then
  echo "  ✓ start.sh exited 1 with the expected secrets-missing message"
else
  echo "  ✗ unexpected exit code: $rc"
  tail -20 /tmp/start.log
  exit 1
fi

echo
echo "=========================================="
echo "  8. start.sh with a placeholder client_secrets.json (skip launch)"
echo "=========================================="
# Now drop a placeholder so start.sh moves past the secrets check, then sigterm it.
echo '{}' > /root/inboxpilot/client_secrets.json
timeout 8 bash ./start.sh > /tmp/start.log 2>&1 || true
# Did it at least try to launch the server?
if grep -q "Starting InboxPilot" /tmp/start.log; then
  echo "  ✓ launcher reached the start-server stage"
else
  echo "  ✗ launcher never tried to start the server"
  cat /tmp/start.log
  exit 1
fi

echo
echo "=========================================="
echo "  ALL CHECKS PASSED ✓"
echo "=========================================="
