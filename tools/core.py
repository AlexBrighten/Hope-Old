"""
tools/core.py — Foundational tools: web search, page fetching, workspace
file management, long-term memory, and time.

Refactored from the original monolithic tools.py with project-relative
path resolution (works on both Linux and Windows).
"""

import datetime
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

WORKSPACE = (HERE / "workspace").resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
MEMORY = WORKSPACE / "memory.md"


def _safe(path: str) -> Path:
    """Resolve a path inside the workspace; reject escapes."""
    p = (WORKSPACE / path).resolve()
    if p != WORKSPACE and WORKSPACE not in p.parents:
        raise ValueError("Path is outside the workspace folder")
    return p


# ── Web ─────────────────────────────────────────────────────────────────

def search_web(query: str, max_results: int = 5) -> list:
    """Search the web. Returns title, url and snippet for each result."""
    try:
        try:
            from ddgs import DDGS
            with DDGS() as d:
                results = d.text(query, max_results=max_results)
            return [
                {"title": r["title"], "url": r["href"], "snippet": r["body"]}
                for r in results
            ]
        except ImportError:
            # Fallback to duckduckgo_search or html scrape
            from duckduckgo_search import DDGS
            with DDGS() as d:
                results = list(d.text(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ]
    except Exception as e:
        return [{"error": f"Search unavailable: {e}. Please ensure ddgs or duckduckgo-search is installed."}]


def fetch_page(url: str, max_chars: int = 6000) -> str:
    """Fetch a web page and return its readable text."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        return f"Error fetching {url}: {e}"

    # Try trafilatura first
    try:
        import trafilatura
        text = trafilatura.extract(r.text)
        if text:
            return text[:max_chars]
    except ImportError:
        pass

    # Fallback to BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:max_chars] or "No readable text found."
    except Exception as e:
        return f"Error extracting page text: {e}"


# ── Workspace Files ─────────────────────────────────────────────────────

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
        return _safe(path).read_text(encoding="utf-8")[:max_chars]
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """Write (or overwrite) a text file in the workspace folder."""
    try:
        p = _safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Saved {path}"
    except Exception as e:
        return f"Error: {e}"


# ── Memory ──────────────────────────────────────────────────────────────

def remember(note: str) -> str:
    """Save a note to long-term memory so it can be recalled in later chats."""
    stamp = datetime.date.today().isoformat()
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY, "a", encoding="utf-8") as f:
        f.write(f"- ({stamp}) {note}\n")
    return "Remembered."


def recall() -> str:
    """Return everything saved in long-term memory."""
    return MEMORY.read_text(encoding="utf-8") if MEMORY.exists() else "Memory is empty."


# ── Time ────────────────────────────────────────────────────────────────

def current_time() -> str:
    """Return the current date and time."""
    return datetime.datetime.now().strftime("%A, %d %B %Y, %H:%M")


# ── Legacy email (backward compat — prefer gmail_tool for new code) ────

def send_email_to_me(subject: str, body: str) -> str:
    """Email the owner. It can only ever send to the owner's own address."""
    import smtplib
    from email.message import EmailMessage

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


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    search_web, fetch_page,
    list_files, read_file, write_file,
    remember, recall, current_time,
    send_email_to_me,
]
