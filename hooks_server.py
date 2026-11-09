"""
hooks_server.py — Secure localhost webhook receiver for Hope.

Security hardening:
  • Binds strictly to 127.0.0.1 (localhost only).
  • Verifies GitHub HMAC-SHA256 signature (X-Hub-Signature-256) using GITHUB_WEBHOOK_SECRET.
  • Prevents unauthorized external triggers.

Start with: python hooks_server.py
"""

import hashlib
import hmac
import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

HOOKS_PORT = int(os.environ.get("HOOKS_PORT", "8000"))
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()
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


def verify_github_signature(raw_body: bytes, signature_header: str | None) -> tuple[bool, str]:
    """Verify GitHub HMAC-SHA256 signature header."""
    if not GITHUB_WEBHOOK_SECRET:
        return False, "GITHUB_WEBHOOK_SECRET is not configured in .env. Webhook rejected for security."
    if not signature_header:
        return False, "Missing X-Hub-Signature-256 header."
    if not signature_header.startswith("sha256="):
        return False, "Invalid signature format — expected 'sha256=<hash>'."

    expected_sig = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received_sig = signature_header[len("sha256="):]

    if hmac.compare_digest(expected_sig, received_sig):
        return True, ""
    return False, "HMAC signature mismatch."


# ── Built-in Standard Library HTTP Fallback ─────────────────────────────

class WebhookHTTPHandler(BaseHTTPRequestHandler):
    """Standard-library handler binding strictly to 127.0.0.1."""

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "agent": "Hope",
                "mode": "http.server",
                "bound": "127.0.0.1",
                "github_secret_configured": bool(GITHUB_WEBHOOK_SECRET),
            })
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
        raw_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        raw_str = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_str) if raw_str else {}
        except Exception:
            payload = {"raw": raw_str[:500]}

        if self.path.startswith("/webhook/github"):
            # Verify GitHub HMAC signature
            sig_header = self.headers.get("X-Hub-Signature-256")
            valid, err = verify_github_signature(raw_bytes, sig_header)
            if not valid:
                self.log_message("GitHub webhook rejected: %s", err)
                self._send_json(401, {"error": "Unauthorized", "detail": err})
                return

            event_type = self.headers.get("X-GitHub-Event", "unknown")
            _log_event("github", event_type, payload)
            self._send_json(200, {"received": True, "event": event_type})

        elif self.path.startswith("/webhook/custom/"):
            source = self.path.split("/webhook/custom/")[-1]
            _log_event(source, "custom", payload)
            self._send_json(200, {"received": True, "source": source})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        print(f"[Webhook 127.0.0.1] {format % args}")


def run_server():
    """Run FastAPI if available, otherwise run built-in HTTP server."""
    try:
        from fastapi import FastAPI, Request, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn

        app = FastAPI(title="Hope Webhook Receiver", version="1.0.0")

        @app.get("/health")
        async def health():
            return {
                "status": "ok",
                "agent": "Hope",
                "mode": "fastapi",
                "bound": "127.0.0.1",
                "github_secret_configured": bool(GITHUB_WEBHOOK_SECRET),
            }

        @app.post("/webhook/github")
        async def github_webhook(request: Request):
            raw_body = await request.body()
            sig_header = request.headers.get("X-Hub-Signature-256")
            valid, err = verify_github_signature(raw_body, sig_header)
            if not valid:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Unauthorized", "detail": err},
                )

            event_type = request.headers.get("X-GitHub-Event", "unknown")
            try:
                payload = await request.json()
            except Exception:
                payload = {"raw": raw_body.decode(errors="replace")[:500]}
            _log_event("github", event_type, payload)
            return {"received": True, "event": event_type}

        @app.post("/webhook/custom/{source}")
        async def custom_webhook(source: str, request: Request):
            raw_body = await request.body()
            try:
                payload = await request.json()
            except Exception:
                payload = {"raw": raw_body.decode(errors="replace")[:500]}
            _log_event(source, "custom", payload)
            return {"received": True, "source": source}

        @app.get("/webhooks/log")
        async def get_webhook_log():
            events = []
            if LOG_FILE.exists():
                lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
                events = [json.loads(line) for line in lines[-20:]]
            return {"events": events}

        print(f"Hope FastAPI webhook server starting strictly on 127.0.0.1:{HOOKS_PORT}...")
        uvicorn.run(app, host="127.0.0.1", port=HOOKS_PORT)

    except ImportError:
        print(f"Hope standard-library webhook server starting strictly on 127.0.0.1:{HOOKS_PORT}...")
        httpd = HTTPServer(("127.0.0.1", HOOKS_PORT), WebhookHTTPHandler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()


if __name__ == "__main__":
    run_server()
