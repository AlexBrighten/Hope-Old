import os

import requests
from dotenv import load_dotenv

load_dotenv()
t = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not t:
    raise SystemExit("TELEGRAM_BOT_TOKEN is missing in .env")
try:
    r = requests.get(f"https://api.telegram.org/bot{t}/getUpdates", timeout=20).json()
except Exception as e:
    raise SystemExit("request failed: " + type(e).__name__)
if not r.get("ok"):
    raise SystemExit("Telegram rejected the token. Check it in .env")
found = False
for u in r.get("result", []):
    m = u.get("message") or {}
    c = m.get("chat") or {}
    print("chat id:", c.get("id"), "| name:", c.get("first_name"), "| text:", m.get("text"))
    found = True
if not found:
    print("No messages yet. Send your bot a message in Telegram, then rerun.")
