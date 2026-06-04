import os
import threading
import time
import webbrowser
from pathlib import Path

import typer
import uvicorn

app = typer.Typer(name="todo-mail", help="Email-to-Todo Assistant")


@app.command()
def start(
    port: int = typer.Option(8765, help="Port to listen on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
):
    """Authenticate with Google (if needed) then start the server."""
    from .db import init_db
    from .mail import ensure_authenticated
    from .settings import get_secret

    init_db()

    typer.echo("Checking Google credentials...")
    try:
        ensure_authenticated()
        typer.echo("Authenticated with Google.")
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)

    api_key = get_secret("groq-api-key") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        typer.echo(
            "Warning: no Groq API key set — email classification disabled.\n"
            "Run 'todo-mail set-api-key' to configure it.",
            err=True,
        )

    if not no_browser:
        def _open():
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{port}")
        threading.Thread(target=_open, daemon=True).start()

    typer.echo(f"Starting todo-mail on http://127.0.0.1:{port}")
    uvicorn.run("todo_mail.app:app", host="127.0.0.1", port=port, reload=False)


@app.command()
def set_api_key():
    """Save your Groq API key to the macOS Keychain."""
    from .settings import set_secret
    key = typer.prompt("Groq API key", hide_input=True)
    set_secret("groq-api-key", key)
    typer.echo("Saved. Restart todo-mail start for it to take effect.")


@app.command()
def reauth():
    """Clear stored Google credentials and re-authenticate on next start."""
    from .settings import delete_secret
    delete_secret("google-oauth")
    typer.echo("Cleared. Run 'todo-mail start' to re-authenticate.")


@app.command()
def label(
    n: int = typer.Option(20, help="Max number of emails to label in this session"),
):
    """Interactively label emails to build the evaluation gold set."""
    from .db import init_db
    init_db()
    from .eval import run_label
    run_label(n)


@app.command(name="eval")
def run_eval():
    """Re-classify every gold-labeled email with Claude and report quality metrics."""
    from .db import init_db
    init_db()
    from .eval import run_eval as _run_eval
    _run_eval()


_SLACK_SCOPES = "im:history  im:read  mpim:history  mpim:read  users:read  search:read"


@app.command(name="slack-auth")
def slack_auth():
    """Save a Slack user token to the macOS Keychain and verify it works."""
    from .slack_client import SlackClient, save_slack_token

    typer.echo(
        "\nSlack setup\n"
        "───────────\n"
        "1. Go to https://api.slack.com/apps → create or open your app\n"
        "2. Left sidebar → OAuth & Permissions\n"
        "3. Scroll to 'Scopes' → 'User Token Scopes' (NOT Bot Token Scopes, NOT App-Level Tokens)\n"
        f"4. Add these scopes:\n"
        f"     {_SLACK_SCOPES}\n"
        "5. Scroll back to the top of that same page\n"
        "   → click 'Install to Workspace' (or 'Reinstall to Workspace' if already installed)\n"
        "   → click Allow\n"
        "6. The 'User OAuth Token' (xoxp-…) appears on that page — copy it\n"
        "\n"
        "Note: Bot tokens (xoxb-) and App-Level tokens (xapp-) will NOT work.\n"
    )
    token = typer.prompt("Paste your User OAuth Token (xoxp-…)", hide_input=True)
    token = token.strip()

    if token.startswith("xapp-"):
        typer.echo(
            "Error: that looks like an App-Level Token (xapp-). "
            "You need the User OAuth Token from the OAuth & Permissions page (starts with xoxp-).",
            err=True,
        )
        raise typer.Exit(code=1)

    client = SlackClient(token)
    try:
        info = client.test_auth()
    except Exception as exc:
        typer.echo(f"Error: Slack rejected the token — {exc}", err=True)
        raise typer.Exit(code=1)

    # Verify DM scopes are present
    try:
        client._get("conversations.list", types="im", limit=1)
    except RuntimeError as exc:
        if "missing_scope" in str(exc):
            typer.echo(
                f"Error: token is valid but missing required scopes.\n"
                f"Go to OAuth & Permissions → User Token Scopes, add:\n"
                f"  {_SLACK_SCOPES}\n"
                f"Then reinstall the app to your workspace.",
                err=True,
            )
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    save_slack_token(token)
    typer.echo(
        f"Connected to workspace '{info.get('team')}' as '{info.get('user')}'. "
        "Restart todo-mail to enable Slack polling."
    )


@app.command(name="slack-logout")
def slack_logout():
    """Remove stored Slack credentials."""
    from .slack_client import delete_slack_token
    delete_slack_token()
    typer.echo("Slack token removed. Restart todo-mail to disable Slack polling.")


@app.command()
def setup():
    """Print setup instructions for Google OAuth credentials."""
    target = Path.home() / "inboxpilot" / "client_secrets.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    typer.echo(f"""
Setup instructions
──────────────────
1. Go to https://console.cloud.google.com/
2. Create a project (or select an existing one)
3. Enable these APIs:
     • Gmail API
     • Google Calendar API
     • People API
     • Contacts API
4. APIs & Services → Credentials → Create credentials → OAuth 2.0 Client ID
5. Application type: Desktop app
6. Download the JSON file and rename it to:  client_secrets.json
7. Move it into this folder (already created for you):
     {target.parent}

Then run:  todo-mail start
""")
    target.parent.mkdir(parents=True, exist_ok=True)
