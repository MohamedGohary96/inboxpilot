import logging
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

_CALENDAR_NAME = "Replies"
_SOURCE_KEY = "source"
_SOURCE_VAL = "todo-mail"

_client: "CalendarClient | None" = None


def init_calendar(creds: Credentials) -> None:
    global _client
    _client = CalendarClient(creds)


def get_calendar() -> "CalendarClient | None":
    return _client


def clear_calendar() -> None:
    global _client
    _client = None


class CalendarClient:
    def __init__(self, creds: Credentials):
        self._creds = creds
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._calendar_id: str | None = None

    def _get_or_create_calendar(self) -> str:
        if self._calendar_id:
            return self._calendar_id

        page_token: str | None = None
        while True:
            resp = self._svc.calendarList().list(pageToken=page_token).execute()
            for item in resp.get("items", []):
                if item.get("summary") == _CALENDAR_NAME:
                    self._calendar_id = item["id"]
                    return self._calendar_id
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        new_cal = self._svc.calendars().insert(
            body={
                "summary": _CALENDAR_NAME,
                "description": "Reply-by deadlines managed by todo-mail",
            }
        ).execute()
        self._calendar_id = new_cal["id"]
        logger.info("Created '%s' calendar: %s", _CALENDAR_NAME, self._calendar_id)
        return self._calendar_id

    def _is_owned_event(self, cal_id: str, event_id: str) -> bool:
        """Return True only if the event has source=todo-mail extended property."""
        try:
            event = self._svc.events().get(calendarId=cal_id, eventId=event_id).execute()
            props = event.get("extendedProperties", {}).get("private", {})
            return props.get(_SOURCE_KEY) == _SOURCE_VAL
        except HttpError as e:
            if e.resp.status == 404:
                return False
            raise

    def create_event(
        self,
        task_id: int,
        subject: str,
        summary: str | None,
        reply_by: datetime,
        thread_id: str,
    ) -> str:
        """Create a 15-min event ending at reply_by. Returns the event ID."""
        cal_id = self._get_or_create_calendar()
        gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
        start = _aware(reply_by - timedelta(minutes=15))
        end = _aware(reply_by)

        event = (
            self._svc.events()
            .insert(
                calendarId=cal_id,
                body={
                    "summary": f"Reply: {subject}",
                    "description": f"{summary or subject}\n\n{gmail_url}",
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                    "extendedProperties": {
                        "private": {_SOURCE_KEY: _SOURCE_VAL, "task_id": str(task_id)},
                    },
                },
            )
            .execute()
        )
        logger.info("Created calendar event %s for task %d", event["id"], task_id)
        return event["id"]

    def update_event(self, event_id: str, reply_by: datetime) -> None:
        """Move the event when reply_by changes. Skips if not owned by us."""
        try:
            cal_id = self._get_or_create_calendar()
        except HttpError:
            logger.warning("update_event: could not resolve calendar")
            return

        if not self._is_owned_event(cal_id, event_id):
            logger.warning("update_event: %s not owned by todo-mail — skipping", event_id)
            return

        start = _aware(reply_by - timedelta(minutes=15))
        end = _aware(reply_by)
        try:
            self._svc.events().patch(
                calendarId=cal_id,
                eventId=event_id,
                body={
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                },
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                # Calendar was deleted; clear cached ID so next call recreates it
                self._calendar_id = None
                logger.warning("update_event: calendar deleted by user — cleared cached ID")
            else:
                raise

    def delete_event(self, event_id: str) -> None:
        """Delete the event when a task is replied or dismissed."""
        try:
            cal_id = self._get_or_create_calendar()
        except HttpError:
            logger.warning("delete_event: could not resolve calendar")
            return

        if not self._is_owned_event(cal_id, event_id):
            logger.warning("delete_event: %s not owned by todo-mail — skipping", event_id)
            return

        try:
            self._svc.events().delete(calendarId=cal_id, eventId=event_id).execute()
        except HttpError as e:
            if e.resp.status == 404:
                self._calendar_id = None
                logger.debug("delete_event: %s not found or calendar deleted", event_id)
            else:
                logger.warning("delete_event error: %s", e)


    def find_and_book_meeting(
        self,
        date_str: str,
        window_start: str,
        window_end: str,
        duration_minutes: int,
        title: str,
        attendee_email: str,
        attendee_name: str | None = None,
    ) -> dict:
        """Find the first free slot in [window_start, window_end) on date_str and book it.

        date_str: YYYY-MM-DD
        window_start / window_end: HH:MM in local time
        Returns dict with start, end (ISO), html_link, title.
        Raises ValueError if no slot is available.
        """
        tz = datetime.now().astimezone().tzinfo
        y, mo, d = map(int, date_str.split("-"))
        ws_h, ws_m = map(int, window_start.split(":"))
        we_h, we_m = map(int, window_end.split(":"))

        win_start = datetime(y, mo, d, ws_h, ws_m, tzinfo=tz)
        win_end   = datetime(y, mo, d, we_h, we_m, tzinfo=tz)
        slot_dur  = timedelta(minutes=duration_minutes)

        if win_start + slot_dur > win_end:
            raise ValueError("Window is shorter than the requested meeting duration")

        events = self.list_events(win_start.isoformat(), win_end.isoformat(), calendar_id="primary")

        busy: list[tuple[datetime, datetime]] = []
        for ev in events:
            if ev.get("all_day"):
                continue
            try:
                s = datetime.fromisoformat(ev["start"])
                e = datetime.fromisoformat(ev["end"])
                busy.append((_aware(s), _aware(e)))
            except Exception:
                continue
        busy.sort(key=lambda x: x[0])

        cursor = win_start
        for busy_start, busy_end in busy:
            if cursor + slot_dur <= busy_start:
                break
            cursor = max(cursor, busy_end)

        if cursor + slot_dur > win_end:
            raise ValueError("No free slot found in the given window")

        slot_start = cursor
        slot_end   = cursor + slot_dur

        attendee: dict = {"email": attendee_email}
        if attendee_name:
            attendee["displayName"] = attendee_name

        from .settings import get_setting
        my_email = get_setting("account_email") or ""
        attendees = [{"email": my_email, "self": True}] if my_email else []
        attendees.append(attendee)

        event = self._svc.events().insert(
            calendarId="primary",
            sendUpdates="all",
            body={
                "summary": title,
                "start": {"dateTime": slot_start.isoformat()},
                "end":   {"dateTime": slot_end.isoformat()},
                "attendees": attendees,
            },
        ).execute()

        logger.info("Booked meeting '%s' at %s with %s", title, slot_start.isoformat(), attendee_email)
        return {
            "event_id":  event["id"],
            "start":     slot_start.isoformat(),
            "end":       slot_end.isoformat(),
            "html_link": event.get("htmlLink"),
            "title":     title,
        }

    def list_events(self, time_min: str, time_max: str, calendar_id: str = "primary") -> list[dict]:
        """Return all events in [time_min, time_max) across all calendar pages."""
        results: list[dict] = []
        page_token: str | None = None
        while True:
            kwargs: dict = {
                "calendarId": calendar_id,
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 250,
            }
            if page_token:
                kwargs["pageToken"] = page_token
            resp = self._svc.events().list(**kwargs).execute()
            for item in resp.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                start = item.get("start", {})
                end = item.get("end", {})
                all_day = "date" in start and "dateTime" not in start
                results.append({
                    "id": item["id"],
                    "title": item.get("summary") or "(no title)",
                    "start": start.get("dateTime") or start.get("date"),
                    "end": end.get("dateTime") or end.get("date"),
                    "all_day": all_day,
                    "color_id": item.get("colorId"),
                    "description": item.get("description"),
                    "location": item.get("location"),
                    "organizer": _organizer_name(item),
                    "html_link": item.get("htmlLink"),
                    "self_response": _self_response(item),
                })
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results


def _organizer_name(item: dict) -> str | None:
    org = item.get("organizer") or {}
    return org.get("displayName") or org.get("email") or None


def _self_response(item: dict) -> str | None:
    for att in item.get("attendees", []):
        if att.get("self"):
            return att.get("responseStatus")  # accepted / declined / tentative / needsAction
    return None


def _aware(dt: datetime) -> datetime:
    """Attach local timezone if the datetime is naive."""
    return dt if dt.tzinfo else dt.astimezone()
