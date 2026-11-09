import datetime
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests
import trafilatura
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv(Path.home() / "agent" / ".env")

WORKSPACE = (Path.home() / "agent" / "workspace").resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
MEMORY = WORKSPACE / "memory.md"


def _safe(path: str) -> Path:
    p = (WORKSPACE / path).resolve()
    if p != WORKSPACE and WORKSPACE not in p.parents:
        raise ValueError("Path is outside the workspace folder")
    return p


def search_web(query: str, max_results: int = 5) -> list:
    """Search the web. Returns title, url and snippet for each result."""
    try:
        with DDGS() as d:
            results = d.text(query, max_results=max_results)
        return [
            {"title": r["title"], "url": r["href"], "snippet": r["body"]}
            for r in results
        ]
    except Exception as e:
        return [{"error": str(e)}]


def fetch_page(url: str, max_chars: int = 6000) -> str:
    """Fetch a web page and return its readable text."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        return f"Error fetching {url}: {e}"
    text = trafilatura.extract(r.text) or ""
    return text[:max_chars] or "No readable text found."


def list_files(folder: str = ".") -> str:
    """List files in the workspace folder (or a subfolder of it)."""
    try:
        items = sorted(p.name for p in _safe(folder).iterdir())
        return "\n".join(items) or "(empty)"
    except Exception as e:
        return f"Error: {e}"


def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a text file from the workspace folder."""
    try:
        return _safe(path).read_text()[:max_chars]
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a text file in the workspace folder."""
    try:
        p = _safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Saved {path}"
    except Exception as e:
        return f"Error: {e}"


def remember(note: str) -> str:
    """Save a note to long-term memory so it can be recalled in later chats."""
    stamp = datetime.date.today().isoformat()
    with open(MEMORY, "a") as f:
        f.write(f"- ({stamp}) {note}\n")
    return "Remembered."


def recall() -> str:
    """Return everything saved in long-term memory."""
    return MEMORY.read_text() if MEMORY.exists() else "Memory is empty."


def current_time() -> str:
    """Return the current date and time."""
    return datetime.datetime.now().strftime("%A, %d %B %Y, %H:%M")


def send_email_to_me(subject: str, body: str) -> str:
    """Email the owner. It can only ever send to the owner's own address."""
    addr = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not addr or not pw:
        return "Error: email is not configured in .env"
    msg = EmailMessage()
    msg["From"] = addr
    msg["To"] = addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(addr, pw.replace(" ", ""))
            s.send_message(msg)
        return "Email sent."
    except Exception as e:
        return f"Error sending email: {e}"


def get_calendar_events(days_ahead: int = 2) -> str:
    """List the owner's calendar events from today through the next few days."""
    url = os.environ.get("CALENDAR_ICAL_URL")
    if not url:
        return "Error: calendar is not configured in .env"
    try:
        import icalendar
        import recurring_ical_events

        cal = icalendar.Calendar.from_ical(requests.get(url, timeout=20).content)
        today = datetime.date.today()
        end = today + datetime.timedelta(days=days_ahead + 1)
        events = recurring_ical_events.of(cal).between(today, end)
        lines = []
        for e in sorted(events, key=lambda e: str(e["DTSTART"].dt)):
            dt = e["DTSTART"].dt
            if isinstance(dt, datetime.datetime) and dt.tzinfo:
                dt = dt.astimezone()
            lines.append(f"{dt} - {e.get('SUMMARY', '(no title)')}")
        return "\n".join(lines) or "No events in that range."
    except Exception as e:
        return f"Error reading calendar: {e}"


ALL = [search_web, fetch_page, list_files, read_file, write_file,
       remember, recall, current_time, send_email_to_me, get_calendar_events]
