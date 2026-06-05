"""
Runtime configuration loaded from a per-OS user config dir:
  macOS:   ~/Library/Application Support/inboxpilot/config.json
  Linux:   ~/.config/inboxpilot/config.json
  Windows: %APPDATA%\\inboxpilot\\config.json

Create or edit that file to override defaults without reinstalling.
All keys are optional; missing keys fall back to the values in DEFAULTS.

Supported keys
--------------
model           str   Groq model ID (default: llama-3.3-70b-versatile)
prompt_version  str   Prompt version tag stored in classifications (default: v3)
pre_filter      bool  Whether to run the pre-LLM newsletter/bot filter (default: true)
"""

import json
import logging
from pathlib import Path

from platformdirs import user_config_dir

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(user_config_dir("inboxpilot")) / "config.json"

# Legacy location — read transparently if the new one doesn't exist
_LEGACY_CONFIG_PATH = Path.home() / ".config" / "todo-mail" / "config.json"

DEFAULTS: dict = {
    "model":          "llama-3.3-70b-versatile",
    "prompt_version": "v3",
    "pre_filter":     True,
}

_cached: dict | None = None


def load() -> dict:
    """Load config once and cache. Call reload() to pick up file edits."""
    global _cached
    if _cached is not None:
        return _cached
    _cached = _read()
    return _cached


def reload() -> dict:
    """Force a fresh read from disk (e.g. after POST /api/admin/reload-config)."""
    global _cached
    _cached = None
    return load()


def _read() -> dict:
    path = _CONFIG_PATH if _CONFIG_PATH.exists() else _LEGACY_CONFIG_PATH
    if not path.exists():
        return dict(DEFAULTS)
    try:
        with open(path) as f:
            overrides = json.load(f)
        cfg = {**DEFAULTS, **overrides}
        logger.info("Loaded config from %s: model=%s prompt_version=%s",
                    path, cfg["model"], cfg["prompt_version"])
        return cfg
    except Exception as e:
        logger.warning("Could not read %s (%s) — using defaults", path, e)
        return dict(DEFAULTS)
