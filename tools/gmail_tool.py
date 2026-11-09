"""
tools/gmail_tool.py — Full Gmail integration: list, read, send, reply, draft.

Dual-mode authentication:
  1. Primary — Google OAuth via tools.google_auth (Gmail API)
  2. Fallback — IMAP + SMTP with GMAIL_ADDRESS / GMAIL_APP_PASSWORD from .env
  3. If neither is configured, returns setup instructions.
"""

import base64
import email
import email.utils
import imaplib
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from tools.approval import EMAIL_DRAFT_ONLY, check_or_stage

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")


# ── Auth helpers ────────────────────────────────────────────────────────

def _get_gmail_service():
    """Try to build an OAuth Gmail service; return None on failure."""
    try:
        from tools.google_auth import build_service, is_google_oauth_configured
        if is_google_oauth_configured():
            return build_service("gmail", "v1")
    except Exception:
        pass
    return None


def _get_app_creds() -> tuple[str | None, str | None]:
    """Return (GMAIL_ADDRESS, GMAIL_APP_PASSWORD) or (None, None)."""
    addr = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if addr and pw:
        return addr, pw.replace(" ", "")
    return None, None


_SETUP_MSG = (
    "Gmail is not configured. Set up one of:\n"
    "  1. Google OAuth — place credentials.json in the Hope root and run "
    "once to authorise.\n"
    "  2. App password — add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env.\n"
    "See: https://support.google.com/accounts/answer/185833 for app passwords."
)


# ── Helpers: Gmail API body decoding ────────────────────────────────────

def _decode_body(payload: dict) -> str:
    """Recursively extract plain-text body from Gmail API message payload."""
    mime = payload.get("mimeType", "")

    # Direct text/plain part
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Multipart — recurse, prefer text/plain
    parts = payload.get("parts", [])
    for part in parts:
        text = _decode_body(part)
        if text:
            return text

    # Last resort: text/html
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    return ""


def _header(headers: list[dict], name: str) -> str:
    """Extract a header value from Gmail API headers list."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# ── Helpers: IMAP fallback ──────────────────────────────────────────────

def _imap_decode_header(raw: str) -> str:
    """Decode an RFC-2047 encoded header."""
    parts = decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _imap_get_text(msg: email.message.Message) -> str:
    """Extract plain-text body from an email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return "(no plain-text body)"


# ── 1. List messages ───────────────────────────────────────────────────

def gmail_list_messages(query: str = "is:unread", max_results: int = 5) -> str:
    """Search Gmail and return matching messages (ID, subject, sender, date).

    Uses Gmail query syntax, e.g. 'is:unread', 'from:alice subject:meeting',
    'newer_than:1d'.
    """
    # --- OAuth path ---
    service = _get_gmail_service()
    if service:
        try:
            resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = resp.get("messages", [])
            if not messages:
                return f"No messages matching '{query}'."

            lines: list[str] = []
            for m in messages:
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=m["id"], format="metadata",
                         metadataHeaders=["Subject", "From", "Date"])
                    .execute()
                )
                headers = msg.get("payload", {}).get("headers", [])
                lines.append(
                    f"• ID: {m['id']}\n"
                    f"  Subject: {_header(headers, 'Subject')}\n"
                    f"  From: {_header(headers, 'From')}\n"
                    f"  Date: {_header(headers, 'Date')}"
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"Error listing messages via Gmail API: {e}"

    # --- IMAP fallback ---
    addr, pw = _get_app_creds()
    if not addr:
        return _SETUP_MSG

    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(addr, pw)
            imap.select("INBOX")

            # Map common Gmail-style queries to IMAP search
            imap_query = "UNSEEN" if "unread" in query.lower() else "ALL"
            _status, data = imap.search(None, imap_query)
            ids = data[0].split()
            if not ids:
                return f"No messages matching '{query}' (IMAP)."

            ids = ids[-max_results:]  # most recent
            lines: list[str] = []
            for mid in reversed(ids):
                _status, msg_data = imap.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
                raw = msg_data[0][1]  # type: ignore[index]
                msg = email.message_from_bytes(raw)
                lines.append(
                    f"• IMAP UID: {mid.decode()}\n"
                    f"  Subject: {_imap_decode_header(msg.get('Subject', ''))}\n"
                    f"  From: {_imap_decode_header(msg.get('From', ''))}\n"
                    f"  Date: {msg.get('Date', '')}"
                )
            return "\n\n".join(lines)
    except Exception as e:
        return f"Error listing messages via IMAP: {e}"


# ── 2. Read a message ──────────────────────────────────────────────────

def gmail_read_message(message_id: str) -> str:
    """Fetch and return the full content of an email by its message ID.

    Returns subject, from, to, date, and the plain-text body.
    """
    # --- OAuth path ---
    service = _get_gmail_service()
    if service:
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            headers = msg.get("payload", {}).get("headers", [])
            body = _decode_body(msg.get("payload", {}))
            return (
                f"Subject: {_header(headers, 'Subject')}\n"
                f"From: {_header(headers, 'From')}\n"
                f"To: {_header(headers, 'To')}\n"
                f"Date: {_header(headers, 'Date')}\n"
                f"\n{body or '(no text body found)'}"
            )
        except Exception as e:
            return f"Error reading message via Gmail API: {e}"

    # --- IMAP fallback ---
    addr, pw = _get_app_creds()
    if not addr:
        return _SETUP_MSG

    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(addr, pw)
            imap.select("INBOX")
            _status, msg_data = imap.fetch(message_id.encode(), "(RFC822)")
            raw = msg_data[0][1]  # type: ignore[index]
            msg = email.message_from_bytes(raw)
            body = _imap_get_text(msg)
            return (
                f"Subject: {_imap_decode_header(msg.get('Subject', ''))}\n"
                f"From: {_imap_decode_header(msg.get('From', ''))}\n"
                f"To: {_imap_decode_header(msg.get('To', ''))}\n"
                f"Date: {msg.get('Date', '')}\n"
                f"\n{body}"
            )
    except Exception as e:
        return f"Error reading message via IMAP: {e}"


# ── 3. Send email ──────────────────────────────────────────────────────

def gmail_send_email(to: str, subject: str, body: str, approval_token: str = "") -> str:
    """Compose and send an email to any recipient.

    If EMAIL_DRAFT_ONLY is True (default), it safely creates a draft in Gmail
    for manual review instead of sending directly. If draft-only is False,
    it requires human approval via Telegram/chat before transmitting.
    """
    if EMAIL_DRAFT_ONLY:
        draft_res = gmail_create_draft(to, subject, body)
        return (
            f"🛡️ [Draft-Only Mode Active]\n"
            f"Email was NOT sent directly to avoid accidental transmission.\n"
            f"Saved as a DRAFT in your Gmail for your manual review:\n"
            f"• To: {to}\n"
            f"• Subject: {subject}\n"
            f"• Status: {draft_res}"
        )

    # Require explicit human approval before sending
    approved, msg = check_or_stage(
        action_name="gmail_send_email",
        params={"to": to, "subject": subject},
        summary=f"Send email to '{to}' with subject '{subject}'",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    # --- OAuth path ---
    service = _get_gmail_service()
    if service:
        try:
            mime = MIMEText(body)
            mime["To"] = to
            mime["Subject"] = subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            sent = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
            return f"Email sent successfully (ID: {sent['id']})."
        except Exception as e:
            return f"Error sending email via Gmail API: {e}"

    # --- SMTP fallback ---
    addr, pw = _get_app_creds()
    if not addr:
        return _SETUP_MSG

    try:
        msg = EmailMessage()
        msg["From"] = addr
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(addr, pw)
            s.send_message(msg)
        return "Email sent successfully via SMTP."
    except Exception as e:
        return f"Error sending email via SMTP: {e}"


# ── 4. Reply to email ──────────────────────────────────────────────────

def gmail_reply_email(message_id: str, body: str, approval_token: str = "") -> str:
    """Send a threaded reply to an existing email (preserves thread, adds Re: prefix).

    Requires explicit human approval before transmitting.
    """
    approved, msg = check_or_stage(
        action_name="gmail_reply_email",
        params={"message_id": message_id},
        summary=f"Send threaded reply to email ID '{message_id}'",
        approval_token=approval_token,
    )
    if not approved:
        return msg

    # --- OAuth path ---
    service = _get_gmail_service()
    if service:
        try:
            original = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="metadata",
                     metadataHeaders=["Subject", "From", "To", "Message-ID"])
                .execute()
            )
            headers = original.get("payload", {}).get("headers", [])
            thread_id = original.get("threadId", "")
            subject = _header(headers, "Subject")
            reply_to = _header(headers, "From")  # reply to the sender
            orig_msg_id = _header(headers, "Message-ID")

            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            mime = MIMEText(body)
            mime["To"] = reply_to
            mime["Subject"] = subject
            if orig_msg_id:
                mime["In-Reply-To"] = orig_msg_id
                mime["References"] = orig_msg_id

            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            sent = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw, "threadId": thread_id})
                .execute()
            )
            return f"Reply sent successfully (ID: {sent['id']}, thread: {thread_id})."
        except Exception as e:
            return f"Error sending reply via Gmail API: {e}"

    # --- SMTP fallback (limited — no threading) ---
    addr, pw = _get_app_creds()
    if not addr:
        return _SETUP_MSG

    return (
        "Reply threading requires Gmail API (OAuth).  "
        "SMTP fallback cannot preserve threads.  "
        "Use gmail_send_email() to send a regular email instead, "
        "or configure Google OAuth for full reply support."
    )


# ── 5. Create draft ────────────────────────────────────────────────────

def gmail_create_draft(to: str, subject: str, body: str) -> str:
    """Create a draft email in Gmail for manual review before sending.

    Only supported via Gmail API (OAuth).
    """
    service = _get_gmail_service()
    if service:
        try:
            mime = MIMEText(body)
            mime["To"] = to
            mime["Subject"] = subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            draft = (
                service.users()
                .drafts()
                .create(userId="me", body={"message": {"raw": raw}})
                .execute()
            )
            return f"Draft created successfully (Draft ID: {draft['id']})."
        except Exception as e:
            return f"Error creating draft via Gmail API: {e}"

    # --- No SMTP equivalent for drafts ---
    addr, _ = _get_app_creds()
    if addr:
        return (
            "Draft creation requires Gmail API (OAuth).  "
            "SMTP does not support drafts.  "
            "Configure Google OAuth to use this feature."
        )
    return _SETUP_MSG


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    gmail_list_messages,
    gmail_read_message,
    gmail_send_email,
    gmail_reply_email,
    gmail_create_draft,
]
