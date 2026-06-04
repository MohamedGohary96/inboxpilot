from fastapi import APIRouter
from pydantic import BaseModel

from ..settings import DEFAULTS, get_setting, set_setting

router = APIRouter()


@router.get("/settings")
def get_all_settings():
    return {k: get_setting(k) for k in DEFAULTS}


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.post("/settings")
def update_setting(body: SettingUpdate):
    if body.key not in DEFAULTS:
        from fastapi import HTTPException
        raise HTTPException(400, f"unknown setting key '{body.key}'")
    set_setting(body.key, body.value)
    return {"ok": True}
