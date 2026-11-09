"""
briefing.py — Executive Morning Briefing runner for Hope.

Gathers:
  • Current date and time
  • Calendar schedule for today and tomorrow
  • High-priority unread emails
  • Relevant memory notes
And generates a scannable executive briefing.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

import tools
from mcp_agent import NAME, OWNER, MCPAgent

DEFAULT_PROMPT = (
    "Run my executive morning briefing. Call current_time(), calendar_list_events(2), "
    "gmail_list_messages('is:unread', 5), and recall(). Give me:\n"
    "1. Today's and tomorrow's calendar schedule\n"
    "2. Important unread emails that need my attention\n"
    "3. Saved notes or reminders for today\n"
    "Keep it executive-level, concise, and scannable with bullet points."
)

prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT

agent = MCPAgent()
text = agent.ask(prompt)

subject = f"{NAME}: Your Executive Briefing"
if text.startswith(("Agent not ready", "Both brains failed")):
    subject = f"{NAME}: Briefing FAILED"

print(text)

# Attempt to deliver via email if configured
email_result = tools.send_email_to_me(subject, text)
print(f"\n[Delivery Status] {email_result}")
