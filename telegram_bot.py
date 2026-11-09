"""
telegram_bot.py — Telegram mobile interface for Hope AI Agent.
"""

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

from mcp_agent import NAME, OWNER, MCPAgent

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"


def tg(method, **params):
    try:
        return requests.post(f"{API}/{method}", json=params, timeout=70).json()
    except Exception as e:
        print("Telegram error:", type(e).__name__, flush=True)
        return {}


def send(chat_id, text):
    for i in range(0, max(len(text), 1), 4000):
        tg("sendMessage", chat_id=chat_id, text=text[i : i + 4000])


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing in .env")
    if not OWNER_CHAT:
        raise SystemExit("TELEGRAM_CHAT_ID is missing in .env (run chatid.py)")

    agent = MCPAgent()
    status = agent.status()
    print(f"{NAME} is listening on Telegram for owner {OWNER}.", flush=True)
    print(f"Cloud Brain: {status['gemini_model']} | Local Brain: {status['local_brain_model']}", flush=True)

    offset = None
    while True:
        params = {"timeout": 50}
        if offset is not None:
            params["offset"] = offset
        data = tg("getUpdates", **params)
        if not data.get("ok"):
            time.sleep(5)
            continue

        for u in data.get("result", []):
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            text = msg.get("text", "").strip()
            chat = str((msg.get("chat") or {}).get("id", ""))
            if not text or chat != OWNER_CHAT:
                continue

            # Command: /status
            if text.lower() == "/status":
                s = agent.status()
                reply = (
                    f"🤖 *{s['agent_name']} Status*\n\n"
                    f"• *Cloud Brain*: `{s['gemini_model']}` ({'🟢 Ready' if s['gemini_connected'] else '🔴 Missing Key'})\n"
                    f"• *Local Brain*: `{s['local_brain_model']}` ({'🟢 Online' if s['local_brain_available'] else '⚪ Offline'})\n"
                    f"• *Active Tools*: {s['mcp_tools_count']} tools\n\n"
                    f"*Integrations*:\n"
                    f"• GitHub: {'🟢 Active' if s['integrations']['github'] else '⚪ Disabled'}\n"
                    f"• Gmail: {'🟢 Active' if s['integrations']['gmail'] else '⚪ Disabled'}\n"
                    f"• Calendar: {'🟢 Active' if s['integrations']['calendar'] else '⚪ Disabled'}\n"
                    f"• Google Docs: {'🟢 Active' if s['integrations']['gdocs'] else '⚪ Disabled'}\n"
                    f"• Google Sheets: {'🟢 Active' if s['integrations']['gsheets'] else '⚪ Disabled'}\n"
                    f"• Puppeteer: {'🟢 Active' if s['integrations']['puppeteer'] else '⚪ Disabled'}"
                )
                send(chat, reply)
                continue

            # Command: /help
            if text.lower() == "/help":
                reply = (
                    f"Commands for {NAME}:\n"
                    f"• Send any natural message to execute tasks across GitHub, Gmail, Calendar, Browser, Docs, Sheets.\n"
                    f"• `/status` — View connectivity and active brains\n"
                    f"• `/local <text>` — Force local Ollama execution (offline)\n"
                    f"• `/gemini <text>` — Force Gemini cloud execution\n"
                )
                send(chat, reply)
                continue

            tg("sendChatAction", chat_id=chat, action="typing")
            send(chat, agent.ask(text))


if __name__ == "__main__":
    main()
