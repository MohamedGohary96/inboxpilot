import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter()

# email → raw image bytes (or None = no photo found)
_cache: dict[str, bytes | None] = {}

# The signed-in user's own photo (via people/me). Cached at process scope.
# None = looked up and not found; missing key = not looked up yet.
_me_photo: dict[str, bytes | None] = {}


def _get_svc():
    try:
        from ..calendar_client import get_calendar
        cal = get_calendar()
        if not cal:
            return None
        from googleapiclient.discovery import build
        return build("people", "v1", credentials=cal._creds, cache_discovery=False)
    except Exception:
        return None


def _resize(url: str) -> str:
    """Request a 64 px thumbnail instead of the default large size."""
    # Google photo URLs use =s{size} optionally followed by modifiers like -c (crop).
    # Replace only the numeric size, preserving any trailing modifiers.
    if re.search(r'=s\d+', url):
        return re.sub(r'=s\d+', '=s64', url)
    return url + '=s64'


def _fetch_photo_url(email: str) -> str | None:
    svc = _get_svc()
    if not svc:
        return None

    # 1. Workspace domain directory (fast for same-company senders)
    try:
        res = svc.people().searchDirectoryPeople(
            query=email,
            readMask="photos",
            sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
            pageSize=1,
        ).execute()
        for person in res.get("people", []):
            for photo in person.get("photos", []):
                if not photo.get("default"):
                    return _resize(photo["url"])
    except Exception as exc:
        logger.warning("Directory photo lookup failed for %s: %s", email, exc)

    # 2. Saved contacts (covers external senders the user has added)
    try:
        res = svc.people().searchContacts(
            query=email,
            readMask="photos",
            pageSize=1,
        ).execute()
        for result in res.get("results", []):
            for photo in result.get("person", {}).get("photos", []):
                if not photo.get("default"):
                    return _resize(photo["url"])
    except Exception as exc:
        logger.warning("Contact photo lookup failed for %s: %s", email, exc)

    return None


def _fetch_photo_bytes(email: str) -> bytes | None:
    url = _fetch_photo_url(email)
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=5, follow_redirects=True)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            return resp.content
    except Exception as exc:
        logger.warning("Failed to fetch photo bytes for %s: %s", email, exc)
    return None


def clear_photo_cache() -> None:
    _cache.clear()
    _me_photo.clear()


def _fetch_me_photo_bytes() -> bytes | None:
    svc = _get_svc()
    if not svc:
        return None
    try:
        res = svc.people().get(
            resourceName="people/me",
            personFields="photos",
        ).execute()
        for photo in res.get("photos", []):
            if not photo.get("default"):
                url = _resize(photo["url"])
                resp = httpx.get(url, timeout=5, follow_redirects=True)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
                    return resp.content
    except Exception as exc:
        logger.warning("Failed to fetch self photo: %s", exc)
    return None


@router.get("/contacts/photo")
def contact_photo(email: str = Query(...)):
    if email in _cache:
        data = _cache[email]
        if data:
            return Response(content=data, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(404)

    if not _get_svc():
        # Auth not ready; don't cache so the next request retries
        raise HTTPException(404)

    data = _fetch_photo_bytes(email)
    _cache[email] = data
    if data:
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404)


@router.get("/me/photo")
def me_photo():
    if "data" in _me_photo:
        data = _me_photo["data"]
        if data:
            return Response(content=data, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(404)

    if not _get_svc():
        raise HTTPException(404)

    data = _fetch_me_photo_bytes()
    _me_photo["data"] = data
    if data:
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404)
