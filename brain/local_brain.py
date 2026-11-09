"""
brain/local_brain.py — Ollama-powered local co-processor for Hope.

Handles lightweight tasks: intent classification, content summarisation,
memory distillation, and full offline fallback.  Designed for 3B–4B models
running on an Intel Core i7-6600U / 8 GB RAM Debian system.
"""

import json
import threading
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent.parent
CFG = json.loads((HERE / "config.json").read_text())

OLLAMA_URL = CFG.get("ollama_url", "http://localhost:11434")
PREFERRED_MODEL = CFG.get("local_model", "llama3.2:3b")
CANDIDATES = CFG.get("local_model_candidates", [
    "llama3.2:3b", "phi3.5", "qwen2.5:3b", "gemma-3-4b", "qwen2.5:1.5b",
])
MEMORY_FILE = HERE / "workspace" / "memory.md"


class LocalBrain:
    """Thin wrapper around a local Ollama model."""

    def __init__(self):
        self._lock = threading.Lock()
        self.active_model: str | None = None
        self._resolve_model()

    # ── model discovery ─────────────────────────────────────────────────
    def list_installed_models(self) -> list[str]:
        """Query Ollama for locally-available model tags."""
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def _resolve_model(self):
        """Pick the best installed model from the candidate list."""
        installed = self.list_installed_models()
        if not installed:
            self.active_model = PREFERRED_MODEL      # optimistic fallback
            return
        # normalise: ollama tags may include version suffixes like ":3b" or ":latest"
        installed_base = {m.split(":")[0]: m for m in installed}
        for candidate in [PREFERRED_MODEL] + CANDIDATES:
            base = candidate.split(":")[0]
            if base in installed_base:
                self.active_model = installed_base[base]
                return
        # nothing from candidates found — just use whatever is installed
        self.active_model = installed[0]

    # ── core generation ─────────────────────────────────────────────────
    def generate(self, prompt: str, *, model: str | None = None,
                 system: str = "", max_tokens: int = 1024,
                 temperature: float = 0.3) -> str:
        """Send a prompt to the local Ollama model and return the reply."""
        model = model or self.active_model
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if system:
            payload["system"] = system
        try:
            with self._lock:
                resp = requests.post(
                    f"{OLLAMA_URL}/api/generate", json=payload, timeout=120,
                )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            return f"[local-brain-error] {e}"

    # ── intent classification ───────────────────────────────────────────
    def classify_intent(self, user_prompt: str) -> str:
        """Return 'local' or 'cloud' based on query complexity.

        * local  — greetings, simple questions, memory lookups, rewrites
        * cloud  — tool use, coding, multi-step reasoning, API operations
        """
        system = (
            "You are an intent classifier. Given a user message, reply with "
            "exactly one word: 'local' if the message is a greeting, simple "
            "factual question, memory recall, text rewrite, or casual chat; "
            "'cloud' if it requires external tools (GitHub, email, calendar, "
            "browser, Notion, Docs), code generation, complex analysis, or "
            "multi-step reasoning. Reply ONLY with 'local' or 'cloud'."
        )
        result = self.generate(user_prompt, system=system, max_tokens=8,
                               temperature=0.0)
        token = result.strip().lower().split()[0] if result.strip() else "cloud"
        return token if token in ("local", "cloud") else "cloud"

    # ── summarisation ───────────────────────────────────────────────────
    def summarize_content(self, text: str, *, max_words: int = 150) -> str:
        """Compress long text (emails, web pages) into a tight summary."""
        system = (
            f"Summarise the following content in at most {max_words} words. "
            "Keep key facts, dates, names, and action items. Be concise."
        )
        # Truncate extremely long input to avoid overwhelming the local model
        return self.generate(text[:6000], system=system, max_tokens=512)

    # ── memory distillation ─────────────────────────────────────────────
    def distill_memories(self, conversation_text: str) -> str:
        """Extract lasting facts from a conversation and append to memory."""
        system = (
            "You are a memory archivist. From the conversation below, extract "
            "ONLY enduring personal facts, preferences, or commitments the "
            "owner has stated (e.g. 'Prefers dark mode', 'Sister's birthday "
            "is March 12', 'Works at Acme Corp'). Output one bullet point per "
            "fact. If there are no lasting facts, reply with NONE."
        )
        result = self.generate(conversation_text[:4000], system=system,
                               max_tokens=512, temperature=0.1)
        if not result or "NONE" in result.upper():
            return "No new memories to save."
        import datetime
        stamp = datetime.date.today().isoformat()
        lines = [
            f"- ({stamp}) {line.lstrip('- •').strip()}"
            for line in result.strip().splitlines()
            if line.strip() and line.strip().upper() not in ("NONE", "-")
        ]
        if lines:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        return f"Saved {len(lines)} new memory note(s)."

    # ── quick chat ──────────────────────────────────────────────────────
    def chat(self, user_prompt: str, owner: str = "Alex") -> str:
        """Handle a lightweight chat query entirely locally."""
        system = (
            f"You are Hope, a friendly personal AI assistant for {owner}. "
            "Answer concisely and helpfully. If you don't know something, "
            "say so honestly."
        )
        # Include recent memory for context
        memory = ""
        if MEMORY_FILE.exists():
            memory = "\n\nSaved notes about the owner:\n" + \
                     MEMORY_FILE.read_text(encoding="utf-8")[-2000:]
        return self.generate(user_prompt, system=system + memory,
                             max_tokens=512, temperature=0.5)

    # ── health check ────────────────────────────────────────────────────
    def is_available(self) -> bool:
        """Return True if Ollama is reachable and has at least one model."""
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

