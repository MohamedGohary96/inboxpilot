from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..settings import DEFAULTS, get_setting, set_setting

router = APIRouter()

_KEY_PREFIXES: dict[str, str] = {
    "groq":      "gsk_",
    "openai":    "sk-",
    "anthropic": "sk-ant-",
}


@router.get("/settings")
def get_all_settings():
    return {k: get_setting(k) for k in DEFAULTS}


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.post("/settings")
def update_setting(body: SettingUpdate):
    if body.key not in DEFAULTS:
        raise HTTPException(400, f"unknown setting key '{body.key}'")
    set_setting(body.key, body.value)
    return {"ok": True}


# ── Generic LLM provider key endpoints ────────────────────────────────────────

@router.get("/settings/llm-key/status")
def llm_key_status(provider: str = "groq"):
    from ..classify import has_provider_api_key
    return {"has_key": has_provider_api_key(provider)}


class LlmKeyUpdate(BaseModel):
    provider: str
    key: str


@router.post("/settings/llm-key")
def update_llm_key(body: LlmKeyUpdate):
    provider = (body.provider or "").strip()
    key = (body.key or "").strip()

    if not key:
        raise HTTPException(400, "API key is empty")

    prefix = _KEY_PREFIXES.get(provider)
    if prefix and not key.startswith(prefix):
        raise HTTPException(400, f"{provider.capitalize()} API keys start with '{prefix}'")

    try:
        from ..classify import set_provider_api_key
        set_provider_api_key(provider, key)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Could not save key: {exc}")
    return {"ok": True}


# ── Legacy Groq-specific endpoints (kept for backwards compatibility) ──────────

@router.get("/settings/groq-key/status")
def groq_key_status():
    from ..classify import has_groq_api_key
    return {"has_key": has_groq_api_key()}


class GroqKeyUpdate(BaseModel):
    key: str


@router.post("/settings/groq-key")
def update_groq_key(body: GroqKeyUpdate):
    key = (body.key or "").strip()
    if not key:
        raise HTTPException(400, "API key is empty")
    if not key.startswith("gsk_"):
        raise HTTPException(400, "Groq API keys start with 'gsk_'")
    try:
        from ..classify import set_groq_api_key
        set_groq_api_key(key)
    except Exception as exc:
        raise HTTPException(500, f"Could not save key: {exc}")
    return {"ok": True}
