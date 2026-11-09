"""
telegram_bot.py — Secure Telegram mobile interface for Hope AI Agent.

Security features:
  • Strictly ignores every chat ID except the configured TELEGRAM_CHAT_ID.
  • Interactive Human-in-the-Loop approval gate: reply "yes" or "no" to approve
    or reject high-impact mutating actions (commits, PRs, sends, deletions).
"""

import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

from mcp_agent import NAME, OWNER, MCPAgent
from tools.approval import approve_action, reject_action, _pending, _load_pending

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
        tg("sendMessage", chat_id=chat_id, text=text[i : i + 4000], parse_mode="Markdown")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing in .env")
    if not OWNER_CHAT:
        raise SystemExit("TELEGRAM_CHAT_ID is missing in .env (run chatid.py)")

    agent = MCPAgent()
    status = agent.status()
    owner_chat_str = OWNER_CHAT.strip()

    print("═══════════════════════════════════════════")
    print(f"  {NAME} is listening on Telegram.")
    print(f"  Security Lock: Bound STRICTLY to Chat ID {owner_chat_str}")
    print(f"  (All other chats will be silently dropped and logged)")
    print("═══════════════════════════════════════════", flush=True)

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

            # Extract message or callback query
            msg = u.get("message") or u.get("edited_message") or {}
            chat = str((msg.get("chat") or {}).get("id", "")).strip()
            text = msg.get("text", "").strip()

            # ── STRICT CHAT ID VALIDATION ─────────────────────────────────
            # Reject every single message from any unauthorized chat ID
            if not chat or chat != owner_chat_str:
                if chat:
                    print(f"🛡️ [SECURITY BLOCKED] Dropped message from unauthorized chat ID: {chat}", flush=True)
                continue

            if not text:
                continue

            lower_text = text.lower().strip()

            # ── HUMAN APPROVAL HANDLERS ("yes" / "no") ───────────────────
            # Matches: "yes", "approve", "yes act-1234", "approve act-1234"
            if re.match(r"^(yes|approve|confirm)(\s+act-[a-f0-9]+)?$", lower_text):
                match = re.search(r"act-[a-f0-9]+", lower_text)
                target_id = match.group(0) if match else None
                success, reply_msg = approve_action(target_id)
                emoji = "✅" if success else "⚠️"
                send(chat, f"{emoji} {reply_msg}\n\nHope is now authorized to proceed with this task.")
                continue

            # Matches: "no", "reject", "cancel", "no act-1234", "reject act-1234"
            if re.match(r"^(no|reject|cancel)(\s+act-[a-f0-9]+)?$", lower_text):
                match = re.search(r"act-[a-f0-9]+", lower_text)
                target_id = match.group(0) if match else None
                success, reply_msg = reject_action(target_id)
                send(chat, f"🛑 {reply_msg}")
                continue

            # Command: /pending or /actions
            if lower_text in ("/pending", "/actions"):
                _load_pending()
                pending_items = [v for v in _pending.values() if v.status == "pending"]
                if not pending_items:
                    send(chat, "ℹ️ No pending actions awaiting approval.")
                else:
                    lines = ["📋 *Pending Actions Awaiting Approval*:"]
                    for p in pending_items:
                        lines.append(f"• `{p.action_id}`: *{p.action_name}*\n  {p.summary}")
                    lines.append("\nReply `yes <id>` to approve or `no <id>` to cancel.")
                    send(chat, "\n".join(lines))
                continue

            # Command: /status
            if lower_text == "/status":
                s = agent.status()
                reply = (
                    f"🤖 *{s['agent_name']} Status Report*\n\n"
                    f"• *Cloud Brain*: `{s['gemini_model']}` ({'🟢 Ready' if s['gemini_connected'] else '🔴 Missing Key'})\n"
                    f"• *Local Brain*: `{s['local_brain_model']}` ({'🟢 Online' if s['local_brain_available'] else '⚪ Offline'})\n"
                    f"• *Active Tools*: {s['mcp_tools_count']} tools\n"
                    f"• *Security Lock*: Verified Chat ID `{owner_chat_str}`\n\n"
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
            if lower_text == "/help":
                reply = (
                    f"Commands for {NAME}:\n\n"
                    f"• Send any natural instruction to execute tasks across GitHub, Gmail, Calendar, Browser, Docs, Sheets.\n"
                    f"• `yes` / `no` — Approve or reject staged mutating actions (email sends, commits, PRs, calendar deletes).\n"
                    f"• `/pending` — View actions currently awaiting your approval.\n"
                    f"• `/status` — View connectivity and active brains.\n"
                    f"• `/local <text>` — Force local Ollama execution (offline).\n"
                    f"• `/gemini <text>` — Force Gemini cloud execution."
                )
                send(chat, reply)
                continue

            tg("sendChatAction", chat_id=chat, action="typing")
            send(chat, agent.ask(text))


if __name__ == "__main__":
    main()
