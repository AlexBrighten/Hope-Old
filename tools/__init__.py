"""
tools package for Hope AI agent.

Exports:
  • ALL_TOOLS: Master list of all registered FastMCP tool functions.
  • ALL: Alias for backward compatibility with original Hope code.
"""

from tools.core import ALL as CORE_TOOLS
from tools.core import (
    search_web, fetch_page,
    list_files, read_file, write_file,
    remember, recall, current_time,
    send_email_to_me,
)

from tools.github_tool import ALL as GITHUB_TOOLS
from tools.github_tool import (
    github_list_repos, github_get_repo_info,
    github_read_file, github_create_or_update_file,
    github_list_issues, github_create_issue, github_comment_issue,
    github_list_prs, github_create_pr, github_search_code,
)

from tools.gmail_tool import ALL as GMAIL_TOOLS
from tools.gmail_tool import (
    gmail_list_messages, gmail_read_message,
    gmail_send_email, gmail_reply_email, gmail_create_draft,
)

from tools.calendar_tool import ALL as CALENDAR_TOOLS
from tools.calendar_tool import (
    calendar_list_events, calendar_create_event,
    calendar_update_event, calendar_delete_event,
    calendar_quick_add,
)

from tools.gdocs_tool import ALL as GDOCS_TOOLS
from tools.gdocs_tool import (
    gdocs_create_document, gdocs_read_document,
    gdocs_append_text, gdocs_search_documents,
)

from tools.gsheets_tool import ALL as GSHEETS_TOOLS
from tools.gsheets_tool import (
    gsheets_create_spreadsheet, gsheets_read_range,
    gsheets_write_range, gsheets_append_rows,
    gsheets_get_sheet_names, gsheets_search_spreadsheets,
)

from tools.browser_tool import ALL as BROWSER_TOOLS
from tools.browser_tool import (
    browser_open_and_read, browser_take_screenshot,
    browser_interact, browser_capture_api,
)

# Backward-compatibility alias for original get_calendar_events
def get_calendar_events(days_ahead: int = 2) -> str:
    """List the owner's calendar events from today through the next few days."""
    return calendar_list_events(days_ahead=days_ahead)


ALL_TOOLS = (
    CORE_TOOLS
    + GITHUB_TOOLS
    + GMAIL_TOOLS
    + CALENDAR_TOOLS
    + GDOCS_TOOLS
    + GSHEETS_TOOLS
    + BROWSER_TOOLS
)

# Alias for server.py and backward compatibility
ALL = ALL_TOOLS
