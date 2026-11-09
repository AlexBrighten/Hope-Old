"""
tools/approval.py — Human-in-the-loop approval gate for mutating actions.

Gates high-impact operations:
  • Email sending (draft-only by default or requires explicit approval)
  • GitHub file commits and PR creations
  • GitHub issue comments and creations
  • Google Calendar event deletions

Dispatches real-time approval requests to the Hope Web Dashboard and
optional free mobile push notifications via ntfy.sh (zero-cost, no account needed).
"""

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

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

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", CFG.get("ntfy_topic", "")).strip()
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:8080").rstrip("/")


@dataclass
class PendingAction:
    action_id: str
    action_name: str
    params: dict
    summary: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | approved | rejected | executed | expired

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "params": self.params,
            "summary": self.summary,
            "created_at": self.created_at,
            "status": self.status,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.created_at)),
        }


# In-memory registry of pending actions (persisted to workspace/pending_actions.json)
_pending: dict[str, PendingAction] = {}
_ACTION_FILE = HERE / "workspace" / "pending_actions.json"


def _save_pending():
    try:
        _ACTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in _pending.items()}
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
                    params=v.get("params", {}),
                    summary=v.get("summary", ""),
                    created_at=v.get("created_at", time.time()),
                    status=v.get("status", "pending"),
                )
                for k, v in data.items()
            }
        except Exception:
            _pending = {}


_load_pending()


def _notify_push(action: PendingAction):
    """Dispatch free mobile push notification via ntfy.sh with 1-tap Approve/Reject buttons."""
    if not NTFY_TOPIC:
        return

    try:
        url = f"https://ntfy.sh/{NTFY_TOPIC}"
        approve_endpoint = f"{WEB_BASE_URL}/api/approvals/{action.action_id}/approve"
        reject_endpoint = f"{WEB_BASE_URL}/api/approvals/{action.action_id}/reject"
        view_endpoint = f"{WEB_BASE_URL}/#approvals"

        headers = {
            "Title": f"🚨 Hope Action Approval: {action.action_name}",
            "Priority": "urgent",
            "Tags": "warning,shield,robot",
            # ntfy action buttons: open dashboard, or execute HTTP POST directly
            "Actions": (
                f"view, Open Dashboard, {view_endpoint}; "
                f"http, Approve, {approve_endpoint}, method=POST, clear=true; "
                f"http, Reject, {reject_endpoint}, method=POST, clear=true"
            ),
        }

        body = (
            f"Action: {action.action_name}\n"
            f"Details: {action.summary}\n"
            f"ID: {action.action_id}"
        )

        requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=5)
    except Exception as e:
        print(f"[Approval Gate] ntfy push notification failed: {e}")


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

    # Dispatch mobile push notification if configured
    _notify_push(act)
    return act


def get_action_status(action_id: str) -> str:
    """Return status: 'pending', 'approved', 'rejected', 'executed', or 'expired'."""
    _load_pending()
    act = _pending.get(action_id)
    if not act:
        return "not_found"
    # Actions expire after 30 minutes
    if act.status == "pending" and (time.time() - act.created_at > 1800):
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
        pending_list = [a for a in _pending.values() if a.status == "pending"]
        act = sorted(pending_list, key=lambda a: a.created_at, reverse=True)[0] if pending_list else None

    if not act:
        return False, "No matching pending action found to approve."
    if time.time() - act.created_at > 1800:
        act.status = "expired"
        _save_pending()
        return False, f"Action `{act.action_id}` has expired (30m timeout)."

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


def list_pending_actions() -> list[dict]:
    """Return all actions currently pending approval."""
    _load_pending()
    now = time.time()
    results = []
    for act in sorted(_pending.values(), key=lambda a: a.created_at, reverse=True):
        if act.status == "pending":
            if now - act.created_at > 1800:
                act.status = "expired"
            else:
                results.append(act.to_dict())
    _save_pending()
    return results


def list_all_actions(limit: int = 50) -> list[dict]:
    """Return recent actions regardless of status."""
    _load_pending()
    sorted_acts = sorted(_pending.values(), key=lambda a: a.created_at, reverse=True)
    return [a.to_dict() for a in sorted_acts[:limit]]


def clear_resolved_actions() -> int:
    """Purge approved, rejected, or expired actions to keep registry lean."""
    _load_pending()
    global _pending
    before = len(_pending)
    _pending = {k: v for k, v in _pending.items() if v.status == "pending"}
    _save_pending()
    return before - len(_pending)


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
        f"Staged in Hope Web Dashboard (Action ID: `{act.action_id}`).\n\n"
        f"Details: {summary}\n\n"
        f"To approve, click 'Approve' in your Hope Web Dashboard or reply 'yes {act.action_id}'."
    )
