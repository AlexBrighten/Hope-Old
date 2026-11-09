"""
tools/gsheets_tool.py — Google Sheets tools: create, read, write, append, and search spreadsheets.

Uses Google Sheets API v4 for spreadsheet operations and Google Drive API v3 for
spreadsheet discovery. Credentials are managed by tools.google_auth.
"""

import json
import re
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

_SETUP_MSG = (
    "Google OAuth is not configured. To set up:\n"
    "1. Go to Google Cloud Console → APIs & Services → Library.\n"
    "2. Enable Google Sheets API and Google Drive API.\n"
    "3. Ensure credentials.json is in the Hope project root.\n"
    "4. Run Hope again — it will open a browser for one-time consent."
)

_SHEET_URL_PATTERN = re.compile(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)")


def _extract_sheet_id(spreadsheet_id_or_url: str) -> str:
    """Extract a Google Sheets ID from a URL or return the raw ID."""
    raw = spreadsheet_id_or_url.strip()
    match = _SHEET_URL_PATTERN.search(raw)
    return match.group(1) if match else raw


def _get_sheets_service():
    """Build a Google Sheets API v4 service client."""
    try:
        from tools.google_auth import build_service, is_google_oauth_configured
    except ImportError:
        return None, _SETUP_MSG
    if not is_google_oauth_configured():
        return None, _SETUP_MSG
    try:
        return build_service("sheets", "v4"), None
    except Exception as e:
        return None, f"Error building Sheets service: {e}"


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


def gsheets_create_spreadsheet(title: str, sheet_names: str = "Sheet1") -> str:
    """Create a new Google Spreadsheet and return its URL and ID.

    Args:
        title: Title of the new spreadsheet.
        sheet_names: Comma-separated list of sheet/tab names (default "Sheet1").

    Returns title, spreadsheet ID, and direct URL.
    """
    service, err = _get_sheets_service()
    if err:
        return err

    try:
        names = [n.strip() for n in sheet_names.split(",") if n.strip()] or ["Sheet1"]
        body = {
            "properties": {"title": title},
            "sheets": [{"properties": {"title": name}} for name in names],
        }
        resp = service.spreadsheets().create(body=body).execute()
        sheet_id = resp["spreadsheetId"]
        url = resp.get("spreadsheetUrl", f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        return (
            f"Created Google Spreadsheet:\n"
            f"• Title: {title}\n"
            f"• ID: `{sheet_id}`\n"
            f"• URL: {url}\n"
            f"• Sheets: {', '.join(names)}"
        )
    except Exception as e:
        return f"Error creating spreadsheet: {e}"


def gsheets_read_range(spreadsheet_id_or_url: str, range_name: str = "A1:Z100") -> str:
    """Read a range of cells from a Google Spreadsheet.

    Args:
        spreadsheet_id_or_url: Document ID or full Google Sheets URL.
        range_name: Cell range to read, e.g. "Sheet1!A1:D10" or "A1:Z50".

    Returns formatted table of values.
    """
    service, err = _get_sheets_service()
    if err:
        return err

    sheet_id = _extract_sheet_id(spreadsheet_id_or_url)
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=range_name)
            .execute()
        )
        rows = result.get("values", [])
        if not rows:
            return f"No data found in range '{range_name}'."

        # Format as markdown-friendly table
        lines = []
        for i, row in enumerate(rows):
            formatted_row = " | ".join(str(cell) for cell in row)
            lines.append(f"| {formatted_row} |")
            if i == 0 and len(rows) > 1:
                # Add header separator
                sep = " | ".join("---" for _ in row)
                lines.append(f"| {sep} |")

        return f"Spreadsheet Range `{range_name}` ({len(rows)} rows):\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Error reading range '{range_name}': {e}"


def gsheets_write_range(spreadsheet_id_or_url: str, range_name: str, values_json: str) -> str:
    """Write or overwrite cell values in a specified range.

    Args:
        spreadsheet_id_or_url: Document ID or full Google Sheets URL.
        range_name: Starting range, e.g. "Sheet1!A1" or "A1:C3".
        values_json: JSON array of row arrays, e.g. '[["Name", "Score"], ["Alex", 98]]'.

    Returns update confirmation with updated cell count.
    """
    service, err = _get_sheets_service()
    if err:
        return err

    sheet_id = _extract_sheet_id(spreadsheet_id_or_url)
    try:
        parsed_values = json.loads(values_json)
        if not isinstance(parsed_values, list):
            return "Error: values_json must be a JSON array of row arrays."

        # If a single flat list was provided, wrap it into a 2D array
        if parsed_values and not isinstance(parsed_values[0], list):
            parsed_values = [parsed_values]

        body = {"values": parsed_values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )
        updated_cells = result.get("updatedCells", 0)
        updated_range = result.get("updatedRange", range_name)
        return f"Successfully updated {updated_cells} cells in `{updated_range}`."
    except json.JSONDecodeError as e:
        return f"Error parsing values_json: {e}. Provide valid JSON array of arrays."
    except Exception as e:
        return f"Error writing to range '{range_name}': {e}"


def gsheets_append_rows(spreadsheet_id_or_url: str, range_name: str, rows_json: str) -> str:
    """Append one or more rows to the end of a sheet table.

    Args:
        spreadsheet_id_or_url: Document ID or full Google Sheets URL.
        range_name: Sheet or range to append to, e.g. "Sheet1" or "Sheet1!A:D".
        rows_json: JSON array of row arrays, e.g. '[["Task 1", "Done", "2026-11-10"]]'.

    Returns append confirmation with range appended.
    """
    service, err = _get_sheets_service()
    if err:
        return err

    sheet_id = _extract_sheet_id(spreadsheet_id_or_url)
    try:
        parsed_rows = json.loads(rows_json)
        if not isinstance(parsed_rows, list):
            return "Error: rows_json must be a JSON array."
        if parsed_rows and not isinstance(parsed_rows[0], list):
            parsed_rows = [parsed_rows]

        body = {"values": parsed_rows}
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        updates = result.get("updates", {})
        updated_range = updates.get("updatedRange", range_name)
        updated_rows = updates.get("updatedRows", len(parsed_rows))
        return f"Appended {updated_rows} row(s) to `{updated_range}`."
    except json.JSONDecodeError as e:
        return f"Error parsing rows_json: {e}."
    except Exception as e:
        return f"Error appending rows: {e}"


def gsheets_get_sheet_names(spreadsheet_id_or_url: str) -> str:
    """List all tabs/sheets and their IDs in a Google Spreadsheet.

    Args:
        spreadsheet_id_or_url: Document ID or full Google Sheets URL.

    Returns tab names, sheet IDs, and row/column counts.
    """
    service, err = _get_sheets_service()
    if err:
        return err

    sheet_id = _extract_sheet_id(spreadsheet_id_or_url)
    try:
        spreadsheet = (
            service.spreadsheets()
            .get(spreadsheetId=sheet_id, fields="properties.title,sheets.properties")
            .execute()
        )
        title = spreadsheet.get("properties", {}).get("title", "Untitled")
        sheets = spreadsheet.get("sheets", [])
        lines = [f"Spreadsheet: **{title}** (`{sheet_id}`)"]
        for s in sheets:
            props = s.get("properties", {})
            name = props.get("title", "Unnamed")
            sid = props.get("sheetId", 0)
            grid = props.get("gridProperties", {})
            rows = grid.get("rowCount", 0)
            cols = grid.get("columnCount", 0)
            lines.append(f"• **{name}** (ID: {sid}) — {rows} rows × {cols} cols")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching sheet tabs: {e}"


def gsheets_search_spreadsheets(query: str = "", max_results: int = 10) -> str:
    """Search Google Drive for spreadsheets matching a query string.

    Args:
        query: Search term for filename or contents.
        max_results: Maximum spreadsheets to return (default 10).

    Returns list of matching spreadsheets with titles, IDs, and links.
    """
    drive, err = _get_drive_service()
    if err:
        return err

    try:
        clauses = ["mimeType = 'application/vnd.google-apps.spreadsheet'", "trashed = false"]
        if query.strip():
            safe_query = query.replace("'", "\\'")
            clauses.append(f"name contains '{safe_query}'")
        q_str = " and ".join(clauses)

        results = (
            drive.files()
            .list(
                q=q_str,
                pageSize=max_results,
                fields="files(id, name, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = results.get("files", [])
        if not files:
            return f"No Google Spreadsheets found matching '{query}'."

        lines = [f"Found {len(files)} spreadsheet(s):"]
        for f in files:
            name = f.get("name", "Untitled")
            fid = f.get("id")
            url = f.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{fid}/edit")
            lines.append(f"• **{name}**\n  ID: `{fid}`\n  URL: {url}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching spreadsheets: {e}"


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    gsheets_create_spreadsheet,
    gsheets_read_range,
    gsheets_write_range,
    gsheets_append_rows,
    gsheets_get_sheet_names,
    gsheets_search_spreadsheets,
]

