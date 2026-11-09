"""
tools/calendar_tool.py — Google Calendar tools: list, create, update,
delete, and quick-add events.

Primary path uses Google Calendar API v3 via OAuth.
Fallback (list only) uses an iCal URL for read-only access.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

_SETUP_INSTRUCTIONS = (
    "Google Calendar is not configured.\n"
    "Option 1 (full access): Set up Google OAuth —\n"
    "  1. Download credentials.json from Google Cloud Console.\n"
    "  2. Place it in the Hope project root.\n"
    "  3. Run Hope once to complete the browser consent flow.\n"
    "Option 2 (read-only listing): Add CALENDAR_ICAL_URL to your .env file\n"
    "  with your Google Calendar secret iCal address."
)


def _get_service():
    """Try to build a Calendar API service; returns None on failure."""
    try:
        from tools.google_auth import build_service, is_google_oauth_configured
    except ImportError:
        return None
    if not is_google_oauth_configured():
        return None
    try:
        return build_service("calendar", "v3")
    except Exception:
        return None


def _ical_url() -> str | None:
    return os.environ.get("CALENDAR_ICAL_URL")


def _require_write_access():
    """Return an error string if write access is unavailable, else None."""
    svc = _get_service()
    if svc is not None:
        return None  # all good
    return (
        "Google OAuth is required for creating/editing events. "
        "iCal provides read-only access.\n" + _SETUP_INSTRUCTIONS
    )


def _format_event(event: dict) -> str:
    """Format a Calendar API event dict into a readable string."""
    eid = event.get("id", "?")
    summary = event.get("summary", "(no title)")
    start = event.get("start", {})
    end = event.get("end", {})
    start_str = start.get("dateTime", start.get("date", "?"))
    end_str = end.get("dateTime", end.get("date", "?"))
    location = event.get("location", "")
    description = (event.get("description") or "")[:120]

    lines = [f"• {summary}", f"  ID: {eid}", f"  When: {start_str} → {end_str}"]
    if location:
        lines.append(f"  Where: {location}")
    if description:
        lines.append(f"  Notes: {description}")
    return "\n".join(lines)


# ── List Events ─────────────────────────────────────────────────────────


def calendar_list_events(days_ahead: int = 7, max_results: int = 15) -> str:
    """List upcoming Google Calendar events.

    Args:
        days_ahead: How many days into the future to look (default 7).
        max_results: Maximum number of events to return (default 15).

    Returns a formatted list with event ID, summary, start/end times,
    location, and a description snippet.
    """
    # --- Try Google Calendar API first ---
    service = _get_service()
    if service is not None:
        try:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = result.get("items", [])
            if not events:
                return f"No events in the next {days_ahead} day(s)."
            header = f"📅 {len(events)} event(s) in the next {days_ahead} day(s):\n"
            return header + "\n\n".join(_format_event(e) for e in events)
        except Exception as e:
            return f"Error listing events via Calendar API: {e}"

    # --- Fallback: iCal URL (read-only) ---
    ical_url = _ical_url()
    if not ical_url:
        return _SETUP_INSTRUCTIONS

    try:
        import requests
        from icalendar import Calendar
        from recurring_ical_events import of as recurring_of

        resp = requests.get(ical_url, timeout=30)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        events = recurring_of(cal).between(now, end)

        if not events:
            return f"No events in the next {days_ahead} day(s) (iCal)."

        lines = [f"📅 {len(events)} event(s) (read-only iCal view):\n"]
        for ev in events[:max_results]:
            summary = str(ev.get("SUMMARY", "(no title)"))
            dtstart = ev.get("DTSTART")
            dtend = ev.get("DTEND")
            location = str(ev.get("LOCATION", ""))
            description = str(ev.get("DESCRIPTION", ""))[:120]

            start_str = dtstart.dt.isoformat() if dtstart else "?"
            end_str = dtend.dt.isoformat() if dtend else "?"

            parts = [f"• {summary}", f"  When: {start_str} → {end_str}"]
            if location:
                parts.append(f"  Where: {location}")
            if description:
                parts.append(f"  Notes: {description}")
            lines.append("\n".join(parts))
        return "\n\n".join(lines)
    except ImportError:
        return (
            "iCal libraries not installed. Run:\n"
            "  pip install icalendar recurring-ical-events requests"
        )
    except Exception as e:
        return f"Error fetching iCal calendar: {e}"


# ── Create Event ────────────────────────────────────────────────────────


def calendar_create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create a new Google Calendar event.

    Args:
        summary: Event title.
        start_time: Start in ISO 8601 format (e.g. "2026-11-10T14:00:00+05:30").
        end_time: End in ISO 8601 format.
        description: Optional event description.
        location: Optional location string.

    Returns the event link on success.
    """
    err = _require_write_access()
    if err:
        return err

    service = _get_service()
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    try:
        event = service.events().insert(calendarId="primary", body=body).execute()
        link = event.get("htmlLink", "")
        return f"✅ Event created: {event.get('summary')}\n   Link: {link}"
    except Exception as e:
        return f"Error creating event: {e}"


# ── Update Event ────────────────────────────────────────────────────────


def calendar_update_event(
    event_id: str,
    new_start_time: str = "",
    new_end_time: str = "",
    new_summary: str = "",
    new_description: str = "",
) -> str:
    """Update/reschedule an existing Google Calendar event.

    Only fields with non-empty values are changed.

    Args:
        event_id: The event ID (from calendar_list_events).
        new_start_time: New start time in ISO 8601 (optional).
        new_end_time: New end time in ISO 8601 (optional).
        new_summary: New title (optional).
        new_description: New description (optional).
    """
    err = _require_write_access()
    if err:
        return err

    service = _get_service()
    updates: dict = {}
    if new_summary:
        updates["summary"] = new_summary
    if new_description:
        updates["description"] = new_description
    if new_start_time:
        updates["start"] = {"dateTime": new_start_time}
    if new_end_time:
        updates["end"] = {"dateTime": new_end_time}

    if not updates:
        return "Nothing to update — provide at least one field to change."

    try:
        event = (
            service.events()
            .patch(calendarId="primary", eventId=event_id, body=updates)
            .execute()
        )
        return (
            f"✅ Event updated: {event.get('summary')}\n"
            f"   Link: {event.get('htmlLink', '')}"
        )
    except Exception as e:
        return f"Error updating event: {e}"


# ── Delete Event ────────────────────────────────────────────────────────


def calendar_delete_event(event_id: str) -> str:
    """Delete/cancel a Google Calendar event by its ID.

    Args:
        event_id: The event ID (from calendar_list_events).
    """
    err = _require_write_access()
    if err:
        return err

    service = _get_service()
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return f"✅ Event {event_id} deleted."
    except Exception as e:
        return f"Error deleting event: {e}"


# ── Quick Add ───────────────────────────────────────────────────────────


def calendar_quick_add(text: str) -> str:
    """Create an event from natural language using Google Calendar's quickAdd.

    Examples: "Dinner with Sarah tomorrow at 7pm at Italian Place",
              "Team standup every weekday at 9am".

    Args:
        text: Natural language description of the event.
    """
    err = _require_write_access()
    if err:
        return err

    service = _get_service()
    try:
        event = (
            service.events()
            .quickAdd(calendarId="primary", text=text)
            .execute()
        )
        return (
            f"✅ Quick-add event created: {event.get('summary', text)}\n"
            f"   When: {event.get('start', {}).get('dateTime', event.get('start', {}).get('date', '?'))}\n"
            f"   Link: {event.get('htmlLink', '')}"
        )
    except Exception as e:
        return f"Error quick-adding event: {e}"


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    calendar_list_events,
    calendar_create_event,
    calendar_update_event,
    calendar_delete_event,
    calendar_quick_add,
]
