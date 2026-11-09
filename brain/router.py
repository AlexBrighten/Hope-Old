"""
brain/router.py — Intelligent query dispatcher for the Dual-Brain architecture.

Routes user messages to either the local Ollama brain (fast, free, offline)
or the cloud Gemini brain (powerful, multi-tool) based on intent classification,
explicit user flags, and the configured routing mode.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CFG = json.loads((HERE / "config.json").read_text())
ROUTING_MODE = CFG.get("routing_mode", "auto")

# Keywords / patterns that strongly indicate cloud tools are needed
_CLOUD_KEYWORDS = re.compile(
    r"\b(github|repo|commit|pull request|pr|issue|merge|branch|"
    r"email|gmail|inbox|send mail|draft|reply mail|"
    r"calendar|schedule|meeting|event|reschedule|"
    r"google doc|gdoc|document|"
    r"browse|screenshot|puppeteer|scrape|navigate|"
    r"search the web|look up|fetch|"
    r"write code|debug|refactor|implement|deploy|"
    r"create a|update the|delete the|list my|show my|check my)\b",
    re.IGNORECASE,
)

# Keywords that strongly indicate local handling is fine
_LOCAL_KEYWORDS = re.compile(
    r"\b(hello|hi|hey|good morning|good night|thanks|thank you|"
    r"what is|who is|define|explain briefly|"
    r"rewrite|rephrase|translate|summarize this|"
    r"how are you|what can you do|tell me a joke|"
    r"remember that|what do you know about me)\b",
    re.IGNORECASE,
)


def route_query(user_prompt: str, *, mode: str | None = None) -> str:
    """Decide where to route a user query.

    Returns
    -------
    'local'  — handle with Ollama (fast, free, offline)
    'cloud'  — handle with Gemini + MCP tools (powerful, multi-step)
    """
    mode = mode or ROUTING_MODE

    # ── explicit user overrides ─────────────────────────────────────────
    stripped = user_prompt.strip()
    if stripped.startswith("/local "):
        return "local"
    if stripped.startswith("/gemini ") or stripped.startswith("/cloud "):
        return "cloud"

    # ── forced modes from config ────────────────────────────────────────
    if mode == "local":
        return "local"
    if mode == "gemini":
        return "cloud"

    # ── auto mode: keyword heuristic first (fast, no model call) ────────
    cloud_score = len(_CLOUD_KEYWORDS.findall(user_prompt))
    local_score = len(_LOCAL_KEYWORDS.findall(user_prompt))

    if cloud_score > 0 and cloud_score > local_score:
        return "cloud"
    if local_score > 0 and cloud_score == 0:
        return "local"

    # ── ambiguous: fall back to local model classifier ──────────────────
    try:
        from brain.local_brain import LocalBrain
        lb = LocalBrain()
        if lb.is_available():
            return lb.classify_intent(user_prompt)
    except Exception:
        pass

    # ── ultimate fallback: cloud (safer, has tools) ─────────────────────
    return "cloud"


def strip_routing_prefix(user_prompt: str) -> str:
    """Remove /local, /gemini, /cloud prefixes from the prompt."""
    stripped = user_prompt.strip()
    for prefix in ("/local ", "/gemini ", "/cloud "):
        if stripped.startswith(prefix):
            return stripped[len(prefix):]
    return user_prompt

