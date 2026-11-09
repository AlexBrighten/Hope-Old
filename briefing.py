import sys

import tools
from mcp_agent import NAME, MCPAgent

DEFAULT_PROMPT = (
    "Run my morning briefing. Call current_time(), get_calendar_events(2) and "
    "recall(). Give me: today's schedule, tomorrow's schedule, and anything "
    "from my saved notes that needs attention. Keep it short and scannable."
)

prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT

agent = MCPAgent()
text = agent.ask(prompt)
subject = f"{NAME}: your briefing"
if text.startswith(("Agent not ready", "Both brains failed")):
    subject = f"{NAME}: briefing FAILED"

print(tools.send_email_to_me(subject, text))
