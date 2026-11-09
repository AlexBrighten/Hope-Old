"""
agent.py — Web Chat Interface for Hope AI Agent via Gradio.
"""

import json
from pathlib import Path
import gradio as gr

from mcp_agent import NAME, OWNER, MCPAgent

agent = MCPAgent()
status = agent.status()

print("═══════════════════════════════════════════")
print(f"  {NAME} AI Agent — Dual-Brain Ready")
print(f"  Cloud Brain: {status['gemini_model']} ({'Connected' if status['gemini_connected'] else 'Awaiting API Key'})")
print(f"  Local Brain: {status['local_brain_model']} ({'Ready' if status['local_brain_available'] else 'Offline'})")
print(f"  MCP Tools:   {len(agent.tool_names()) if agent.session else agent.error}")
print("═══════════════════════════════════════════")


def respond(message: str, history: list):
    if message.strip().lower() == "/status":
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
            f"- Browser (Puppeteer): {'🟢 Ready' if s['integrations']['puppeteer'] else '⚪ Not installed'}\n"
        )
        return out
    return agent.ask(message)


description = (
    f"Personal autonomous executive assistant for {OWNER}. "
    "Powered by Dual-Brain architecture (Gemini + Local Ollama). "
    "Equipped with GitHub, Gmail, Calendar, Browser, and Google Docs integrations. "
    "Type `/status` to view active integrations."
)

demo = gr.ChatInterface(
    fn=respond,
    title=f"{NAME} — Personal AI Executive",
    description=description,
)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
