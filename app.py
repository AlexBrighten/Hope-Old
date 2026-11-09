"""
app.py — Modern FastAPI Web Application & API Server for Hope AI Agent.

Serves:
  • Executive Web Dashboard (HTML5, Tailwind CSS, Lucide icons, responsive SPA)
  • Progressive Web App (PWA) with offline shell and installable home screen icon
  • Real-Time Chat with SSE streaming and tool activity indicators
  • Mobile & Desktop Approval Center (1-click Approve/Reject for staged actions)
  • Long-Term Memory Editor (workspace/memory.md)
  • Executive Morning Briefing Generator
  • Dual-Brain Routing & Integration Management
"""

import asyncio
import datetime
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

CFG_FILE = HERE / "config.json"


def load_config() -> dict:
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": "Hope", "owner": "Alex", "routing_mode": "auto"}


def save_config(cfg: dict):
    CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


CFG = load_config()
NAME = CFG.get("name", "Hope")
OWNER = CFG.get("owner", "Alex")
WEB_AUTH_TOKEN = os.environ.get("WEB_AUTH_TOKEN", "").strip()

# Initialize FastAPI
app = FastAPI(
    title=f"{NAME} AI Executive Dashboard",
    description=f"Autonomous AI Executive Agent for {OWNER}",
    version="2.0.0",
)

# CORS middleware for local development and Tailscale subnet access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import Hope agent and approval tools
from mcp_agent import MCPAgent
from tools.approval import (
    approve_action,
    clear_resolved_actions,
    get_action_status,
    list_all_actions,
    list_pending_actions,
    reject_action,
)
from tools.core import recall, remember

agent = MCPAgent()

# ── Pydantic Request Models ───────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []


class MemoryUpdateRequest(BaseModel):
    content: str


class RoutingConfigRequest(BaseModel):
    mode: str  # "auto", "cloud", "local"


# ── Optional Auth Dependency ───────────────────────────────────────────────────


def verify_auth(request: Request):
    """Enforce optional token authentication if WEB_AUTH_TOKEN is configured."""
    if not WEB_AUTH_TOKEN:
        return True
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "token" in request.query_params:
        token = request.query_params["token"]

    if token != WEB_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing authentication token.",
        )
    return True


# ── REST API Endpoints ────────────────────────────────────────────────────────


@app.get("/api/status")
async def get_status(request: Request):
    """Return health, connectivity, and active models for Hope."""
    verify_auth(request)
    st = agent.status()
    pending = list_pending_actions()
    current_cfg = load_config()

    return {
        "status": "online",
        "agent_name": st.get("agent_name", NAME),
        "owner": st.get("owner", OWNER),
        "gemini_model": st.get("gemini_model"),
        "gemini_connected": st.get("gemini_connected", False),
        "local_brain_available": st.get("local_brain_available", False),
        "local_brain_model": st.get("local_brain_model", "none"),
        "mcp_tools_count": st.get("mcp_tools_count", 0),
        "routing_mode": current_cfg.get("routing_mode", "auto"),
        "pending_approvals_count": len(pending),
        "integrations": st.get("integrations", {}),
        "ntfy_configured": bool(os.environ.get("NTFY_TOPIC")),
    }


# ── Persistent Chat Storage ───────────────────────────────────────────────────

CHAT_HISTORY_FILE = HERE / "workspace" / "chat_history.json"
ARCHIVES_DIR = HERE / "workspace" / "chat_archives"


def load_chat_history() -> list[dict]:
    """Load persistent conversation thread from workspace/chat_history.json."""
    if CHAT_HISTORY_FILE.exists():
        try:
            return json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_chat_history(messages: list[dict]):
    """Persist conversation thread to workspace/chat_history.json."""
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHAT_HISTORY_FILE.write_text(json.dumps(messages, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving chat history: {e}")


def append_chat_message(role: str, content: str) -> dict:
    """Append a single message turn to the persistent thread."""
    history = load_chat_history()
    msg_id = f"msg-{secrets.token_hex(4)}"
    now = time.time()
    time_str = time.strftime("%I:%M %p", time.localtime(now))
    entry = {
        "id": msg_id,
        "role": role,
        "content": content,
        "timestamp": now,
        "time_str": time_str,
    }
    history.append(entry)
    # Maintain continuous thread (up to 1,000 turns)
    save_chat_history(history[-1000:])
    return entry


def handle_chat_message(clean: str) -> tuple[str, int]:
    """Execute chat message through approval gates, shortcuts, or Dual-Brain."""
    lower = clean.lower()

    # 1. Quick status check
    if lower == "/status":
        s = agent.status()
        reply = (
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
            f"- Browser (Puppeteer): {'🟢 Ready' if s['integrations']['puppeteer'] else '⚪ Not installed'}"
        )
        return reply, len(list_pending_actions())

    # 2. In-chat approval shortcuts ("yes", "approve act-1234", "no", "reject act-1234")
    if re.match(r"^(yes|approve|confirm)(\s+act-[a-f0-9]+)?$", lower):
        match = re.search(r"act-[a-f0-9]+", lower)
        target_id = match.group(0) if match else None
        success, msg = approve_action(target_id)
        emoji = "✅" if success else "⚠️"
        reply = f"{emoji} {msg}\n\nYou can now tell me to proceed with executing the action."
        return reply, len(list_pending_actions())

    if re.match(r"^(no|reject|cancel)(\s+act-[a-f0-9]+)?$", lower):
        match = re.search(r"act-[a-f0-9]+", lower)
        target_id = match.group(0) if match else None
        success, msg = reject_action(target_id)
        return f"🛑 {msg}", len(list_pending_actions())

    # 3. List pending actions shortcut
    if lower in ("/pending", "/actions"):
        pending_items = list_pending_actions()
        if not pending_items:
            return "ℹ️ No pending actions awaiting approval.", 0
        lines = ["### Pending Actions Awaiting Approval:"]
        for p in pending_items:
            lines.append(f"- **`{p['action_id']}`**: `{p['action_name']}` — {p['summary']}")
        lines.append("\nUse the **Approvals** tab or reply `yes <action_id>` to approve.")
        return "\n".join(lines), len(pending_items)

    # 4. Standard agent execution
    reply = agent.ask(clean)
    pending = list_pending_actions()
    return reply, len(pending)


@app.get("/api/chat/history")
async def get_chat_history(request: Request):
    """Retrieve full continuous conversation thread."""
    verify_auth(request)
    messages = load_chat_history()
    return {"messages": messages, "count": len(messages)}


@app.post("/api/chat/clear")
async def clear_chat_history(request: Request):
    """Archive the current continuous thread and start fresh."""
    verify_auth(request)
    history = load_chat_history()
    if history:
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        archive_file = ARCHIVES_DIR / f"thread_{int(time.time())}.json"
        archive_file.write_text(json.dumps(history, indent=2), encoding="utf-8")
    save_chat_history([])
    agent.history = []
    return {"success": True, "message": "Thread archived and new chat started."}


@app.get("/api/chat/archives")
async def get_chat_archives(request: Request):
    """List archived past chat threads."""
    verify_auth(request)
    if not ARCHIVES_DIR.exists():
        return {"archives": []}
    files = sorted(ARCHIVES_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            first_msg = data[0]["content"][:60] if data else "Empty thread"
            results.append({
                "filename": f.name,
                "timestamp": f.stat().st_mtime,
                "time_str": time.strftime("%b %d, %Y %I:%M %p", time.localtime(f.stat().st_mtime)),
                "count": len(data),
                "preview": first_msg,
            })
        except Exception:
            pass
    return {"archives": results}


@app.post("/api/chat/archives/{filename}/restore")
async def restore_chat_archive(filename: str, request: Request):
    """Restore an archived chat thread into the active thread."""
    verify_auth(request)
    archive_file = ARCHIVES_DIR / filename
    if not archive_file.exists() or not filename.endswith(".json"):
        raise HTTPException(status_code=404, detail="Archive not found.")
    try:
        data = json.loads(archive_file.read_text(encoding="utf-8"))
        save_chat_history(data)
        agent._load_persisted_history()
        return {"success": True, "message": f"Restored thread with {len(data)} messages."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    """Standard conversational endpoint with persistent thread tracking."""
    verify_auth(request)
    clean = req.message.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 1. Permanently record user message
    user_msg = append_chat_message("user", clean)

    # 2. Execute with Dual-Brain
    loop = asyncio.get_event_loop()
    reply, pending_count = await loop.run_in_executor(None, handle_chat_message, clean)

    # 3. Permanently record agent response
    agent_msg = append_chat_message("agent", reply)

    return {
        "reply": reply,
        "pending_count": pending_count,
        "user_msg": user_msg,
        "agent_msg": agent_msg,
    }


@app.get("/api/chat/stream")
async def chat_stream(message: str, request: Request):
    """Server-Sent Events (SSE) stream for live chat responses."""
    verify_auth(request)

    async def event_generator():
        clean = message.strip()
        lower = clean.lower()

        # Handle instant shortcuts
        if lower == "/status" or lower in ("/pending", "/actions") or re.match(r"^(yes|no|approve|reject|confirm|cancel)", lower):
            reply, count = handle_chat_message(clean)
            yield f"data: {json.dumps({'type': 'done', 'reply': reply, 'pending_count': count})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'thought', 'text': 'Analyzing request with Dual-Brain...'})}\n\n"
        await asyncio.sleep(0.05)

        # Run agent query in worker thread
        loop = asyncio.get_event_loop()
        try:
            reply, count = await loop.run_in_executor(None, handle_chat_message, clean)
            yield f"data: {json.dumps({'type': 'done', 'reply': reply, 'pending_count': count})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/approvals")
async def get_approvals(request: Request):
    """Return all pending and recent actions staged for approval."""
    verify_auth(request)
    return {
        "pending": list_pending_actions(),
        "recent": list_all_actions(limit=25),
    }


@app.post("/api/approvals/{action_id}/approve")
async def api_approve_action(action_id: str, request: Request):
    """Approve a specific pending action."""
    verify_auth(request)
    success, message = approve_action(action_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "action_id": action_id}


@app.post("/api/approvals/{action_id}/reject")
async def api_reject_action(action_id: str, request: Request):
    """Reject a specific pending action."""
    verify_auth(request)
    success, message = reject_action(action_id)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "action_id": action_id}


@app.post("/api/approvals/clear")
async def api_clear_approvals(request: Request):
    """Purge resolved/expired actions."""
    verify_auth(request)
    cleared = clear_resolved_actions()
    return {"success": True, "cleared_count": cleared}


@app.get("/api/memory")
async def get_memory(request: Request):
    """Retrieve long-term memory notes from workspace/memory.md."""
    verify_auth(request)
    mem_file = HERE / "workspace" / "memory.md"
    content = ""
    if mem_file.exists():
        try:
            content = mem_file.read_text(encoding="utf-8")
        except Exception as e:
            content = f"Error reading memory: {e}"
    return {"content": content, "path": str(mem_file)}


@app.post("/api/memory")
async def update_memory(req: MemoryUpdateRequest, request: Request):
    """Update long-term memory notes."""
    verify_auth(request)
    mem_file = HERE / "workspace" / "memory.md"
    try:
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        mem_file.write_text(req.content, encoding="utf-8")
        return {"success": True, "message": "Memory notes saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save memory: {e}")


@app.post("/api/briefing")
async def generate_briefing(request: Request):
    """Generate an executive morning briefing across calendar, emails, and tasks."""
    verify_auth(request)
    today_str = datetime.date.today().strftime("%A, %B %d, %Y")
    prompt = (
        f"Generate a concise, professional executive morning briefing for {OWNER} for today, {today_str}. "
        "Check my upcoming Google Calendar events for today, summarize any unread or important Gmail emails, "
        "and review any open GitHub notifications or pending approvals. Format with clean markdown sections: "
        "1. 📅 Today's Schedule & Meetings, 2. 📬 Key Emails & Action Items, 3. 🐙 GitHub & Code Updates, "
        "4. 💡 Executive Recommendation for Today."
    )
    loop = asyncio.get_event_loop()
    briefing_text = await loop.run_in_executor(None, agent.ask, prompt)
    return {"briefing": briefing_text, "date": today_str}


@app.post("/api/config/routing")
async def set_routing_mode(req: RoutingConfigRequest, request: Request):
    """Toggle between 'auto', 'cloud', and 'local' Dual-Brain routing."""
    verify_auth(request)
    mode = req.mode.lower()
    if mode not in ("auto", "cloud", "local"):
        raise HTTPException(status_code=400, detail="Mode must be 'auto', 'cloud', or 'local'.")
    cfg = load_config()
    cfg["routing_mode"] = mode
    save_config(cfg)
    return {"success": True, "mode": mode, "message": f"Brain routing switched to '{mode}' mode."}


# ── Web Application Static Files & Fallback ───────────────────────────────────

WEB_DIR = HERE / "web"
WEB_DIR.mkdir(parents=True, exist_ok=True)

# Mount static directory for CSS, JS, manifest, and icons
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve main SPA dashboard."""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse(
        {
            "message": f"{NAME} API is online. Place index.html into web/ to view dashboard.",
            "status_endpoint": "/api/status",
        }
    )


@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = WEB_DIR / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found")


@app.get("/sw.js")
async def serve_sw():
    sw_path = WEB_DIR / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")


# ── Server Runner ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("WEB_PORT", 8080))
    print("═════════════════════════════════════════════════════════")
    print(f"  ✨ {NAME} Executive Web Dashboard & API Server")
    print(f"  • Local access:     http://localhost:{port}")
    print(f"  • Tailscale/Remote: http://<your-tailscale-ip>:{port}")
    print(f"  • Approvals Gate:   Active (workspace/pending_actions.json)")
    print(f"  • Push Alerts:      {'ntfy.sh/' + os.environ.get('NTFY_TOPIC') if os.environ.get('NTFY_TOPIC') else 'Disabled (set NTFY_TOPIC in .env)'}")
    print("═════════════════════════════════════════════════════════")
    uvicorn.run("app:app", host=host, port=port, reload=False)
