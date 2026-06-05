# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for InboxPilot
# Run from the repo root:  pyinstaller installer/InboxPilot.spec
#
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

repo_root   = Path(SPECPATH).parent          # repo root
backend_dir = repo_root / 'backend'
dist_dir    = repo_root / 'backend' / 'todo_mail' / 'dist'   # built frontend

# ── Hidden imports ────────────────────────────────────────────────────────────
# Packages that are imported dynamically (strings, plugins, etc.) and PyInstaller
# won't detect through static analysis.
hidden = [
    # uvicorn / starlette internals loaded by string
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.loops.asyncio', 'uvicorn.protocols', 'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto', 'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    # FastAPI / starlette
    'starlette.routing', 'starlette.middleware', 'starlette.staticfiles',
    'fastapi.security',
    # Google API client discovers transports dynamically
    'googleapiclient._helpers',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    # keyring backends — loads OS backend at runtime
    'keyring.backends', 'keyring.backends.macOS', 'keyring.backends.SecretService',
    'keyring.backends.Windows', 'keyring.backends.fail',
    # APScheduler triggers/executors loaded by string
    'apscheduler.schedulers.asyncio',
    'apscheduler.executors.asyncio',
    'apscheduler.jobstores.memory',
    'apscheduler.triggers.interval',
    # misc
    'platformdirs', 'rapidfuzz', 'tenacity', 'html2text',
    'python_multipart', 'multipart',
    'email.mime.text', 'email.mime.multipart',
    'sqlite3', '_sqlite3',
]

hidden += collect_submodules('uvicorn')
hidden += collect_submodules('starlette')
hidden += collect_submodules('anyio')
hidden += collect_submodules('todo_mail')

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# Built frontend (HTML/JS/CSS/icons)
if dist_dir.exists():
    datas.append((str(dist_dir), 'todo_mail_dist'))

# httplib2 CA certificates (needed for Google API HTTPS)
datas += collect_data_files('httplib2')

# googleapiclient discovery documents
datas += collect_data_files('googleapiclient')

# pync ships a macOS TerminalNotifier binary
if sys.platform == 'darwin':
    datas += collect_data_files('pync')

# google-auth root certs
datas += collect_data_files('google.auth')
datas += collect_data_files('google.oauth2')

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(repo_root / 'installer' / 'launcher.py')],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest', 'pytest', 'PIL', 'numpy'],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── Mac .app bundle ───────────────────────────────────────────────────────────
if sys.platform == 'darwin':
    icon_path = str(repo_root / 'installer' / 'icon.icns')
    exe = EXE(
        pyz, a.scripts,
        [],
        exclude_binaries=True,
        name='InboxPilot',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,          # no terminal window on double-click
        icon=icon_path if Path(icon_path).exists() else None,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        strip=False,
        upx=True,
        name='InboxPilot',
    )
    app = BUNDLE(
        coll,
        name='InboxPilot.app',
        icon=icon_path if Path(icon_path).exists() else None,
        bundle_identifier='com.inboxpilot.app',
        info_plist={
            'CFBundleDisplayName':      'InboxPilot',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion':          '1',
            'NSHighResolutionCapable':  True,
            'LSUIElement':              False,   # show in Dock
        },
    )

# ── Windows .exe ──────────────────────────────────────────────────────────────
else:
    icon_path = str(repo_root / 'installer' / 'icon.ico')
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas,
        name='InboxPilot',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=False,
        icon=icon_path if Path(icon_path).exists() else None,
    )
