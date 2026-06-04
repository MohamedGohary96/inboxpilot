from fastapi import APIRouter, HTTPException, Query

from ..calendar_client import get_calendar

router = APIRouter()


@router.get("/calendar/events")
def list_calendar_events(
    from_: str = Query(alias="from", description="ISO-8601 datetime with timezone"),
    to: str = Query(description="ISO-8601 datetime with timezone"),
):
    cal = get_calendar()
    if not cal:
        raise HTTPException(503, "Google Calendar not authenticated — run 'todo-mail start'")
    try:
        events = cal.list_events(from_, to)
        return {"events": events}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
