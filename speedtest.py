import time

import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()
c = genai.Client()
Q = "Reply with one short sentence: what is MCP?"

for m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
    t = time.time()
    try:
        c.models.generate_content(model=m, contents=Q)
        print(m, round(time.time() - t, 1), "s")
    except Exception as e:
        print(m, "error:", str(e)[:80])

t = time.time()
requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "qwen2.5:1.5b", "prompt": Q, "stream": False},
    timeout=600,
)
print("qwen local", round(time.time() - t, 1), "s")
