"""
agent.py — Web Chat Interface for Hope AI Agent via Gradio.
"""

import json
from pathlib import Path
import gradio as gr

from mcp_agent import NAME, OWNER, MCPAgent

import re
from tools.approval import approve_action, reject_action, _pending, _load_pending

agent = MCPAgent()
status = agent.status()

print("═══════════════════════════════════════════")
print(f"  {NAME} AI Agent — Dual-Brain Ready")
print(f"  Cloud Brain: {status['gemini_model']} ({'Connected' if status['gemini_connected'] else 'Awaiting API Key'})")
print(f"  Local Brain: {status['local_brain_model']} ({'Ready' if status['local_brain_available'] else 'Offline'})")
print(f"  MCP Tools:   {len(agent.tool_names()) if agent.session else agent.error}")
print("═══════════════════════════════════════════")


def respond(message: str, history: list):
    clean = message.strip()
    lower = clean.lower()

    if lower == "/status":
        s = agent.status()
        out = (
            f"### {s['agent_name']} Status Report\n"
            f"- **Owner**: {s['owner']}\n"
            f"- **Cloud Brain**: `{s['gemini_model']}` ({'🟢 Connected' if s['gemini_connected'] else '🔴 Needs GEMINI_API_KEY'})\n"
            f"- **Local Brain**: `{s['local_brain_model']}` ({'🟢 Online' if s['local_brain_available'] else '⚪ Offline'})\n"
            f"- **Active Tools**: `{s['mcp_tools_count']}` tools registered\n\n"
            f"**Integrations Status**:\n"
            f"- GitHub: {'🟢 Active' if s['integrations']['github'] else '⚪ Not configured'}\n"
            f"- Gmail: {'🟢 Active' if s['integrations']['gmail'] else '⚪ Not configured'}\n"
            f"- Calendar: {'🟢 Active' if s['integrations']['calendar'] else '⚪ Not configured'}\n"
            f"- Google Docs: {'🟢 Active' if s['integrations']['gdocs'] else '⚪ Not configured'}\n"
            f"- Google Sheets: {'🟢 Active' if s['integrations']['gsheets'] else '⚪ Not configured'}\n"
            f"- Browser (Puppeteer): {'🟢 Ready' if s['integrations']['puppeteer'] else '⚪ Not installed'}\n"
        )
        return out

    # Handle human approval ("yes" / "no")
    if re.match(r"^(yes|approve|confirm)(\s+act-[a-f0-9]+)?$", lower):
        match = re.search(r"act-[a-f0-9]+", lower)
        target_id = match.group(0) if match else None
        success, reply_msg = approve_action(target_id)
        emoji = "✅" if success else "⚠️"
        return f"{emoji} {reply_msg}\n\nYou can now tell Hope to proceed with executing the action."

    if re.match(r"^(no|reject|cancel)(\s+act-[a-f0-9]+)?$", lower):
        match = re.search(r"act-[a-f0-9]+", lower)
        target_id = match.group(0) if match else None
        success, reply_msg = reject_action(target_id)
        return f"🛑 {reply_msg}"

    if lower in ("/pending", "/actions"):
        _load_pending()
        pending_items = [v for v in _pending.values() if v.status == "pending"]
        if not pending_items:
            return "ℹ️ No pending actions awaiting approval."
        lines = ["### Pending Actions Awaiting Approval:"]
        for p in pending_items:
            lines.append(f"- **`{p.action_id}`**: `{p.action_name}` — {p.summary}")
        lines.append("\nType `yes <action_id>` to approve or `no <action_id>` to reject.")
        return "\n".join(lines)

    return agent.ask(message)


description = (
    f"Personal autonomous executive assistant for {OWNER}. "
    "Powered by Dual-Brain architecture (Gemini + Local Ollama). "
    "Equipped with GitHub, Gmail, Calendar, Browser, Google Docs, and Google Sheets integrations. "
    "Type `/status` to view active integrations."
)

demo = gr.ChatInterface(
    fn=respond,
    title=f"{NAME} — Personal AI Executive",
    description=description,
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
