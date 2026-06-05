import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter()

_DEST = Path.home() / "inboxpilot" / "client_secrets.json"


@router.post("/setup/credentials")
async def upload_credentials(file: UploadFile = File(...)):
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(400, "File is not valid JSON")
    if "installed" not in data and "web" not in data:
        raise HTTPException(400, "Not a valid Google OAuth credentials file — expected 'installed' or 'web' key")
    _DEST.parent.mkdir(parents=True, exist_ok=True)
    _DEST.write_bytes(content)
    return {"ok": True}
