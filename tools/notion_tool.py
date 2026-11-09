"""
tools/notion_tool.py — Notion integration: search, read, create, and query
pages and databases via the Notion API.

Requires NOTION_API_KEY in .env (create an integration at
https://www.notion.so/my-integrations).
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

_SETUP_MSG = (
    "NOTION_API_KEY is not set. To configure Notion:\n"
    "1. Go to https://www.notion.so/my-integrations and create a new integration.\n"
    "2. Copy the 'Internal Integration Secret'.\n"
    "3. Add  NOTION_API_KEY=<your-secret>  to your .env file.\n"
    "4. In Notion, share the pages/databases you want to access with your integration."
)


def _get_client():
    """Return an authenticated Notion client, or None with an error message."""
    token = os.environ.get("NOTION_API_KEY", "").strip()
    if not token:
        return None, _SETUP_MSG
    try:
        from notion_client import Client
        return Client(auth=token), None
    except Exception as e:
        return None, f"Error creating Notion client: {e}"


# ── Markdown ↔ Notion block helpers ────────────────────────────────────


def _rich_text(text: str) -> list:
    """Wrap a string in Notion rich_text format."""
    return [{"type": "text", "text": {"content": text}}]


def _md_to_blocks(markdown: str) -> list:
    """Convert simple markdown lines to a list of Notion block dicts.

    Supported syntax:
      # Heading 1 / ## Heading 2 / ### Heading 3
      - item            → bulleted_list_item
      1. item           → numbered_list_item
      - [ ] task        → to_do (unchecked)
      - [x] task        → to_do (checked)
      Other lines       → paragraph
    """
    blocks: list = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if not stripped:
            # Empty line → empty paragraph to preserve spacing
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []},
            })
            continue

        # To-do items (must check before bullet)
        m = re.match(r"^- \[([ xX])\]\s+(.*)", stripped)
        if m:
            checked = m.group(1).lower() == "x"
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": _rich_text(m.group(2)),
                    "checked": checked,
                },
            })
            continue

        # Headings
        m = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))  # 1, 2, or 3
            htype = f"heading_{level}"
            blocks.append({
                "object": "block",
                "type": htype,
                htype: {"rich_text": _rich_text(m.group(2))},
            })
            continue

        # Numbered list
        m = re.match(r"^\d+\.\s+(.*)", stripped)
        if m:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _rich_text(m.group(1))},
            })
            continue

        # Bulleted list
        m = re.match(r"^[-*]\s+(.*)", stripped)
        if m:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _rich_text(m.group(1))},
            })
            continue

        # Default: paragraph
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _rich_text(stripped)},
        })

    return blocks


def _block_to_md(block: dict) -> str:
    """Convert a single Notion block dict to a markdown line."""
    btype = block.get("type", "")
    data = block.get(btype, {})

    def _extract_text(rich_text_list: list) -> str:
        return "".join(t.get("plain_text", "") for t in rich_text_list)

    rt = data.get("rich_text", [])
    text = _extract_text(rt)

    if btype == "heading_1":
        return f"# {text}"
    if btype == "heading_2":
        return f"## {text}"
    if btype == "heading_3":
        return f"### {text}"
    if btype == "bulleted_list_item":
        return f"- {text}"
    if btype == "numbered_list_item":
        return f"1. {text}"
    if btype == "to_do":
        check = "x" if data.get("checked") else " "
        return f"- [{check}] {text}"
    if btype == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{text}\n```"
    if btype == "quote":
        return f"> {text}"
    if btype == "divider":
        return "---"
    if btype == "paragraph":
        return text
    # Fallback for unsupported block types
    if text:
        return text
    return ""


def _extract_title(page: dict) -> str:
    """Pull the title string from a Notion page or database object."""
    props = page.get("properties", {})
    # Look for a 'title' type property
    for prop in props.values():
        if prop.get("type") == "title":
            return "".join(
                t.get("plain_text", "") for t in prop.get("title", [])
            )
    # Database objects sometimes have title at top level
    title_list = page.get("title", [])
    if isinstance(title_list, list):
        return "".join(t.get("plain_text", "") for t in title_list)
    return "(untitled)"


# ── Public tool functions ──────────────────────────────────────────────


def notion_search(query: str = "", filter_type: str = "") -> str:
    """Search Notion for pages or databases matching a query.

    Args:
        query: Text to search for. Empty string returns recent items.
        filter_type: 'page', 'database', or '' (both).

    Returns a formatted list of matching items with title, ID, type, and
    last-edited time.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        params: dict = {}
        if query:
            params["query"] = query
        if filter_type in ("page", "database"):
            params["filter"] = {"value": filter_type, "property": "object"}

        resp = client.search(**params)
        results = resp.get("results", [])
        if not results:
            return "No results found."

        lines: list[str] = []
        for item in results:
            obj_type = item.get("object", "unknown")
            item_id = item.get("id", "")
            edited = item.get("last_edited_time", "")
            title = _extract_title(item)
            lines.append(
                f"• [{obj_type.upper()}] {title}\n"
                f"  ID: {item_id}\n"
                f"  Last edited: {edited}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching Notion: {e}"


def notion_read_page(page_id: str) -> str:
    """Retrieve all blocks from a Notion page and return readable markdown.

    Handles headings, paragraphs, bulleted lists, numbered lists, to-do
    items, code blocks, quotes, and dividers.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        # Collect all blocks (handles pagination)
        blocks: list = []
        cursor = None
        while True:
            params: dict = {"block_id": page_id, "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = client.blocks.children.list(**params)
            blocks.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")

        if not blocks:
            return "(empty page)"

        md_lines = [_block_to_md(b) for b in blocks]
        return "\n".join(md_lines)
    except Exception as e:
        return f"Error reading page: {e}"


def notion_create_page(
    parent_page_id: str, title: str, content_markdown: str = ""
) -> str:
    """Create a new child page under an existing Notion page.

    Args:
        parent_page_id: ID of the parent page.
        title: Title for the new page.
        content_markdown: Optional markdown body (# headings, - bullets, etc.).

    Returns confirmation with the new page ID and URL.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        children = _md_to_blocks(content_markdown) if content_markdown else []
        page = client.pages.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            properties={
                "title": [{"type": "text", "text": {"content": title}}],
            },
            children=children,
        )
        page_id = page.get("id", "")
        url = page.get("url", "")
        return f"Page created.\n  ID: {page_id}\n  URL: {url}"
    except Exception as e:
        return f"Error creating page: {e}"


def notion_append_to_page(page_id: str, content_markdown: str) -> str:
    """Append content blocks to an existing Notion page.

    Uses the same markdown conversion as notion_create_page:
    # headings, - bullets, 1. numbered, - [ ] todos, paragraphs.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        blocks = _md_to_blocks(content_markdown)
        if not blocks:
            return "Nothing to append (empty content)."
        client.blocks.children.append(block_id=page_id, children=blocks)
        return f"Appended {len(blocks)} block(s) to page {page_id}."
    except Exception as e:
        return f"Error appending to page: {e}"


def notion_query_database(
    database_id: str, filter_json: str = "", limit: int = 10
) -> str:
    """Query a Notion database and return its rows.

    Args:
        database_id: ID of the database to query.
        filter_json: Optional JSON string for a Notion API filter object.
        limit: Max number of rows to return (default 10).

    Returns formatted rows with their title and other properties.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        params: dict = {"database_id": database_id, "page_size": min(limit, 100)}
        if filter_json:
            params["filter"] = json.loads(filter_json)

        resp = client.databases.query(**params)
        results = resp.get("results", [])
        if not results:
            return "No rows found."

        lines: list[str] = []
        for row in results:
            row_id = row.get("id", "")
            title = _extract_title(row)
            props_summary: list[str] = []
            for pname, pval in row.get("properties", {}).items():
                ptype = pval.get("type", "")
                if ptype == "title":
                    continue  # already shown
                display = _format_property(pval, ptype)
                if display:
                    props_summary.append(f"  {pname}: {display}")

            header = f"• {title}  (ID: {row_id})"
            if props_summary:
                lines.append(header + "\n" + "\n".join(props_summary))
            else:
                lines.append(header)
        return "\n\n".join(lines)
    except json.JSONDecodeError as e:
        return f"Invalid filter_json: {e}"
    except Exception as e:
        return f"Error querying database: {e}"


def _format_property(pval: dict, ptype: str) -> str:
    """Format a Notion property value for display."""
    if ptype == "rich_text":
        return "".join(t.get("plain_text", "") for t in pval.get("rich_text", []))
    if ptype == "number":
        v = pval.get("number")
        return str(v) if v is not None else ""
    if ptype == "select":
        sel = pval.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return ", ".join(s.get("name", "") for s in pval.get("multi_select", []))
    if ptype == "checkbox":
        return "✓" if pval.get("checkbox") else "✗"
    if ptype == "date":
        d = pval.get("date")
        if d:
            start = d.get("start", "")
            end = d.get("end", "")
            return f"{start} → {end}" if end else start
        return ""
    if ptype == "url":
        return pval.get("url", "") or ""
    if ptype == "email":
        return pval.get("email", "") or ""
    if ptype == "phone_number":
        return pval.get("phone_number", "") or ""
    if ptype == "status":
        s = pval.get("status")
        return s.get("name", "") if s else ""
    if ptype == "formula":
        f = pval.get("formula", {})
        return str(f.get(f.get("type", ""), ""))
    # Fallback: return empty for unsupported types
    return ""


def notion_create_database_item(
    database_id: str, title: str, properties_json: str = ""
) -> str:
    """Create a new item (row) in a Notion database.

    Args:
        database_id: ID of the target database.
        title: Title for the new row (set on the database's title property).
        properties_json: Optional JSON string of extra properties, e.g.
            '{"Status": {"select": {"name": "In Progress"}}}'.

    Returns confirmation with the new page ID and URL.
    """
    client, err = _get_client()
    if err:
        return err
    try:
        # First, find the name of the title property in this database
        db_info = client.databases.retrieve(database_id=database_id)
        title_prop_name = "Name"  # default fallback
        for pname, pval in db_info.get("properties", {}).items():
            if pval.get("type") == "title":
                title_prop_name = pname
                break

        properties: dict = {
            title_prop_name: {
                "title": [{"type": "text", "text": {"content": title}}],
            },
        }

        if properties_json:
            extra = json.loads(properties_json)
            properties.update(extra)

        page = client.pages.create(
            parent={"type": "database_id", "database_id": database_id},
            properties=properties,
        )
        page_id = page.get("id", "")
        url = page.get("url", "")
        return f"Database item created.\n  ID: {page_id}\n  URL: {url}"
    except json.JSONDecodeError as e:
        return f"Invalid properties_json: {e}"
    except Exception as e:
        return f"Error creating database item: {e}"


# ── Export ──────────────────────────────────────────────────────────────

ALL = [
    notion_search,
    notion_read_page,
    notion_create_page,
    notion_append_to_page,
    notion_query_database,
    notion_create_database_item,
]
