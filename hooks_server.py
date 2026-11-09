"""
hooks_server.py — Lightweight webhook receiver for Hope.

Listens for incoming HTTP webhooks from GitHub, Notion, or custom
services and logs them to workspace/webhook_log.jsonl.

Supports FastAPI + Uvicorn when installed, with a standard-library
http.server fallback when running in minimal environments.

Start with: python hooks_server.py
"""

import json
import os
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

HOOKS_PORT = int(os.environ.get("HOOKS_PORT", "8000"))
LOG_FILE = HERE / "workspace" / "webhook_log.jsonl"


def _log_event(source: str, event_type: str, payload: dict | str):
    """Append a webhook event to the log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "event_type": event_type,
        "payload_summary": str(payload)[:500],
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Built-in Standard Library HTTP Fallback ─────────────────────────────

class WebhookHTTPHandler(BaseHTTPRequestHandler):
    """Standard-library handler for zero-dependency webhook receiving."""

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "agent": "Hope", "mode": "http.server"})
        elif self.path == "/webhooks/log":
            events = []
            if LOG_FILE.exists():
                lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
                events = [json.loads(line) for line in lines[-20:]]
            self._send_json(200, {"events": events})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except Exception:
            payload = {"raw": raw_body[:500]}

        if self.path.startswith("/webhook/github"):
            event_type = self.headers.get("X-GitHub-Event", "unknown")
            _log_event("github", event_type, payload)
            self._send_json(200, {"received": True, "event": event_type})
        elif self.path.startswith("/webhook/notion"):
            _log_event("notion", "notification", payload)
            self._send_json(200, {"received": True})
        elif self.path.startswith("/webhook/custom/"):
            source = self.path.split("/webhook/custom/")[-1]
            _log_event(source, "custom", payload)
            self._send_json(200, {"received": True, "source": source})
        else:
            _log_event("generic", "post", payload)
            self._send_json(200, {"received": True})

    def log_message(self, format, *args):
        # Clean logging
        print(f"[Webhook] {self.address_string()} - {format % args}")


def run_server():
    """Run FastAPI if available, otherwise run built-in HTTP server."""
    try:
        from fastapi import FastAPI, Request
        import uvicorn

        app = FastAPI(title="Hope Webhook Receiver", version="1.0.0")

        @app.get("/health")
        async def health():
            return {"status": "ok", "agent": "Hope", "mode": "fastapi"}

        @app.post("/webhook/github")
        async def github_webhook(request: Request):
            event_type = request.headers.get("X-GitHub-Event", "unknown")
            try:
                payload = await request.json()
            except Exception:
                payload = {"raw": (await request.body()).decode()[:500]}
            _log_event("github", event_type, payload)
            return {"received": True, "event": event_type}

        @app.post("/webhook/notion")
        async def notion_webhook(request: Request):
            try:
                payload = await request.json()
            except Exception:
                payload = {"raw": (await request.body()).decode()[:500]}
            _log_event("notion", "notification", payload)
            return {"received": True}

        @app.post("/webhook/custom/{source}")
        async def custom_webhook(source: str, request: Request):
            try:
                payload = await request.json()
            except Exception:
                payload = {"raw": (await request.body()).decode()[:500]}
            _log_event(source, "custom", payload)
            return {"received": True, "source": source}

        @app.get("/webhooks/log")
        async def get_webhook_log():
            events = []
            if LOG_FILE.exists():
                lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
                events = [json.loads(line) for line in lines[-20:]]
            return {"events": events}

        print(f"Hope FastAPI webhook server starting on port {HOOKS_PORT}...")
        uvicorn.run(app, host="0.0.0.0", port=HOOKS_PORT)

    except ImportError:
        print(f"Hope standard-library webhook server starting on port {HOOKS_PORT}...")
        httpd = HTTPServer(("0.0.0.0", HOOKS_PORT), WebhookHTTPHandler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()


if __name__ == "__main__":
    run_server()
