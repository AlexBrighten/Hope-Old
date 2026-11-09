"""
tools/approval.py — Human-in-the-loop approval gate for mutating actions.

Gates high-impact operations:
  • Email sending (default: draft-only or requires explicit approval)
  • GitHub file commits and PR creations
  • GitHub issue comments and creations
  • Google Calendar event deletions

Dispatches approval requests via Telegram to the owner's chat ID and supports
interactive confirmation ("yes [action_id]" or "no [action_id]").
"""

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent.parent
load_dotenv(HERE / ".env")

CFG_FILE = HERE / "config.json"
CFG = json.loads(CFG_FILE.read_text(encoding="utf-8")) if CFG_FILE.exists() else {}

# Configuration flags
EMAIL_DRAFT_ONLY = os.environ.get(
    "EMAIL_DRAFT_ONLY",
    str(CFG.get("email_draft_only", True))
).lower() in ("true", "1", "yes")

REQUIRE_APPROVAL = os.environ.get(
    "REQUIRE_APPROVAL",
    str(CFG.get("require_approval", True))
).lower() in ("true", "1", "yes")

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


@dataclass
class PendingAction:
    action_id: str
    action_name: str
    params: dict
    summary: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | approved | rejected | executed


# In-memory registry of pending actions (persisted to workspace/pending_actions.json)
_pending: dict[str, PendingAction] = {}
_ACTION_FILE = HERE / "workspace" / "pending_actions.json"


def _save_pending():
    try:
        _ACTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            k: {
                "action_id": v.action_id,
                "action_name": v.action_name,
                "params": v.params,
                "summary": v.summary,
                "created_at": v.created_at,
                "status": v.status,
            }
            for k, v in _pending.items()
        }
        _ACTION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_pending():
    global _pending
    if _ACTION_FILE.exists():
        try:
            data = json.loads(_ACTION_FILE.read_text(encoding="utf-8"))
            _pending = {
                k: PendingAction(
                    action_id=v["action_id"],
                    action_name=v["action_name"],
                    params=v["params"],
                    summary=v["summary"],
                    created_at=v.get("created_at", time.time()),
                    status=v.get("status", "pending"),
                )
                for k, v in data.items()
            }
        except Exception:
            _pending = {}


_load_pending()


def _notify_telegram(text: str):
    """Send an urgent approval alert to the owner's verified Telegram chat."""
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(
            url,
            json={
                "chat_id": TG_CHAT,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[Approval Gate] Telegram alert failed: {e}")


def stage_action(action_name: str, params: dict, summary: str) -> PendingAction:
    """Stage a mutating action awaiting user approval."""
    action_id = f"act-{secrets.token_hex(2)}"
    act = PendingAction(
        action_id=action_id,
        action_name=action_name,
        params=params,
        summary=summary,
    )
    _pending[action_id] = act
    _save_pending()

    # Dispatch alert to owner's Telegram
    tg_msg = (
        f"🚨 *Action Approval Required*\n\n"
        f"• *Action*: `{action_name}`\n"
        f"• *Details*: {summary}\n"
        f"• *ID*: `{action_id}`\n\n"
        f"Reply with `yes {action_id}` to approve, or `no {action_id}` to reject."
    )
    _notify_telegram(tg_msg)
    return act


def get_action_status(action_id: str) -> str:
    """Return status: 'pending', 'approved', 'rejected', or 'not_found'."""
    _load_pending()
    act = _pending.get(action_id)
    if not act:
        return "not_found"
    # Actions expire after 15 minutes
    if time.time() - act.created_at > 900:
        act.status = "expired"
        _save_pending()
        return "expired"
    return act.status


def approve_action(action_id: str | None = None) -> tuple[bool, str]:
    """Mark an action as approved. If action_id is None, approves the latest pending."""
    _load_pending()
    if action_id:
        act = _pending.get(action_id)
    else:
        # Get latest pending action
        pending_list = [a for a in _pending.values() if a.status == "pending"]
        act = sorted(pending_list, key=lambda a: a.created_at, reverse=True)[0] if pending_list else None

    if not act:
        return False, "No matching pending action found to approve."
    if time.time() - act.created_at > 900:
        act.status = "expired"
        _save_pending()
        return False, f"Action `{act.action_id}` has expired (15m timeout)."

    act.status = "approved"
    _save_pending()
    return True, f"Action `{act.action_id}` ({act.action_name}) is now APPROVED."


def reject_action(action_id: str | None = None) -> tuple[bool, str]:
    """Mark an action as rejected."""
    _load_pending()
    if action_id:
        act = _pending.get(action_id)
    else:
        pending_list = [a for a in _pending.values() if a.status == "pending"]
        act = sorted(pending_list, key=lambda a: a.created_at, reverse=True)[0] if pending_list else None

    if not act:
        return False, "No matching pending action found to reject."

    act.status = "rejected"
    _save_pending()
    return True, f"Action `{act.action_id}` ({act.action_name}) has been REJECTED."


def check_or_stage(
    action_name: str,
    params: dict,
    summary: str,
    approval_token: str = "",
) -> tuple[bool, str]:
    """Check if action is approved; if not, stage it and return request message.

    Returns:
      (True, "") if already approved and ready to execute.
      (False, message) if approval is required and action was staged.
    """
    if not REQUIRE_APPROVAL:
        return True, ""

    # Check if this action was already pre-approved
    if approval_token:
        status = get_action_status(approval_token)
        if status == "approved":
            # Mark executed so it cannot be replayed
            _pending[approval_token].status = "executed"
            _save_pending()
            return True, ""
        elif status == "rejected":
            return False, f"Action `{approval_token}` was REJECTED by owner."
        elif status == "expired":
            return False, f"Action `{approval_token}` has expired."

    # Stage new action
    act = stage_action(action_name, params, summary)
    return False, (
        f"⚠️ APPROVAL REQUIRED before executing '{action_name}'.\n"
        f"A confirmation request has been dispatched to your Telegram.\n\n"
        f"Action ID: `{act.action_id}`\n"
        f"Details: {summary}\n\n"
        f"To approve, reply 'yes {act.action_id}' (or reply 'yes' in Telegram)."
    )

