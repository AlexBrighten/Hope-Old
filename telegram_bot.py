import os
import time

import requests
from dotenv import load_dotenv

from mcp_agent import NAME, MCPAgent

load_dotenv()
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
API = f"https://api.telegram.org/bot{TOKEN}"


def tg(method, **params):
    try:
        return requests.post(f"{API}/{method}", json=params, timeout=70).json()
    except Exception as e:
        # print only the error type, because the message would include the token
        print("telegram error:", type(e).__name__, flush=True)
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
    print(f"{NAME} is listening on Telegram.", flush=True)
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
            text = msg.get("text")
            chat = str((msg.get("chat") or {}).get("id", ""))
            if not text or chat != OWNER_CHAT:
                continue
            tg("sendChatAction", chat_id=chat, action="typing")
            send(chat, agent.ask(text))


if __name__ == "__main__":
    main()
