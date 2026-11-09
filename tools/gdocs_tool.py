"""
tools/gdocs_tool.py — Google Docs tools: create, read, append, and search documents.

Uses Google Docs API v1 for document operations and Google Drive API v3 for
document search/discovery.  Credentials are managed by tools.google_auth.
"""

import re
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

_SETUP_MSG = (
    "Google OAuth is not configured. To set up:\n"
    "1. Go to Google Cloud Console → APIs & Services → Credentials.\n"
    "2. Create an OAuth 2.0 Client ID (Desktop app) and download the JSON.\n"
    "3. Save it as 'credentials.json' in the Hope project root.\n"
    "4. Enable the Google Docs API and Google Drive API for your project.\n"
    "5. Run Hope again — it will open a browser for one-time consent."
)

_DOC_URL_PATTERN = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")


def _get_docs_service():
    """Build a Google Docs API v1 service client."""
    try:
        from tools.google_auth import build_service, is_google_oauth_configured
    except ImportError:
        return None, _SETUP_MSG
    if not is_google_oauth_configured():
        return None, _SETUP_MSG
    try:
        return build_service("docs", "v1"), None
    except Exception as e:
        return None, f"Error building Docs service: {e}"


def _get_drive_service():
    """Build a Google Drive API v3 service client."""
    try:
        from tools.google_auth import build_service, is_google_oauth_configured
    except ImportError:
        return None, _SETUP_MSG
    if not is_google_oauth_configured():
        return None, _SETUP_MSG
    try:
        return build_service("drive", "v3"), None
    except Exception as e:
        return None, f"Error building Drive service: {e}"


def _extract_doc_id(doc_id_or_url: str) -> str:
    """Extract a Google Docs document ID from a URL or return the raw ID.

    Handles URLs like:
        https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit
    """
    match = _DOC_URL_PATTERN.search(doc_id_or_url)
    if match:
        return match.group(1)
    return doc_id_or_url.strip()


def _extract_text(document: dict) -> str:
    """Extract plain-text content from a Google Docs document resource."""
    body = document.get("body", {})
    content = body.get("content", [])
    parts: list[str] = []
    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))
    return "".join(parts)


# ── Public Tools ────────────────────────────────────────────────────────


def gdocs_create_document(title: str, initial_content: str = "") -> str:
    """Create a new Google Doc with the given title and optional initial text.

    Returns the document URL and ID on success.
    """
    service, err = _get_docs_service()
    if err:
        return err
    try:
        doc = service.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]
        url = f"https://docs.google.com/document/d/{doc_id}/edit"

        # Insert initial content if provided
        if initial_content:
            requests_body = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": initial_content,
                    }
                }
            ]
            service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests_body}
            ).execute()

        return (
            f"Document created successfully.\n"
            f"Title: {title}\n"
            f"ID: {doc_id}\n"
            f"URL: {url}"
        )
    except Exception as e:
        return f"Error creating document: {e}"


def gdocs_read_document(document_id_or_url: str) -> str:
    """Read a Google Doc and return its text content.

    Accepts either a document ID or a full Google Docs URL.
    """
    service, err = _get_docs_service()
    if err:
        return err
    doc_id = _extract_doc_id(document_id_or_url)
    try:
        doc = service.documents().get(documentId=doc_id).execute()
        title = doc.get("title", "(untitled)")
        text = _extract_text(doc)
        return f"Title: {title}\n\n{text}" if text.strip() else f"Title: {title}\n\n(empty document)"
    except Exception as e:
        return f"Error reading document '{doc_id}': {e}"


def gdocs_append_text(document_id_or_url: str, text: str) -> str:
    """Append text to the end of an existing Google Doc.

    Accepts either a document ID or a full Google Docs URL.
    """
    service, err = _get_docs_service()
    if err:
        return err
    doc_id = _extract_doc_id(document_id_or_url)
    try:
        # Get the document to find the end index
        doc = service.documents().get(documentId=doc_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"]

        requests_body = [
            {
                "insertText": {
                    "location": {"index": end_index - 1},
                    "text": text,
                }
            }
        ]
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests_body}
        ).execute()

        return f"Text appended to document '{doc_id}' ({len(text)} characters)."
    except Exception as e:
        return f"Error appending to document '{doc_id}': {e}"


def gdocs_search_documents(query: str = "", max_results: int = 10) -> str:
    """Search for Google Docs in the user's Drive.

    Returns matching document titles, IDs, and URLs.
    An empty query returns recent documents.
    """
    service, err = _get_drive_service()
    if err:
        return err
    try:
        q_parts = ["mimeType='application/vnd.google-apps.document'"]
        if query:
            # Escape single quotes in the user query
            safe_query = query.replace("'", "\\'")
            q_parts.append(f"name contains '{safe_query}'")
        q_string = " and ".join(q_parts)

        results = (
            service.files()
            .list(
                q=q_string,
                pageSize=max_results,
                fields="files(id, name, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = results.get("files", [])
        if not files:
            return "No Google Docs found." + (f" (query: '{query}')" if query else "")

        lines: list[str] = [f"Found {len(files)} document(s):"]
        for f in files:
            doc_id = f["id"]
            name = f.get("name", "(untitled)")
            url = f.get("webViewLink", f"https://docs.google.com/document/d/{doc_id}/edit")
            modified = f.get("modifiedTime", "unknown")
            lines.append(f"\n• {name}\n  ID: {doc_id}\n  URL: {url}\n  Modified: {modified}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching documents: {e}"


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    gdocs_create_document,
    gdocs_read_document,
    gdocs_append_text,
    gdocs_search_documents,
]
