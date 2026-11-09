#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
#  setup_debian.sh — Full setup script for Hope AI Agent on Debian
#  Designed for Intel Core i7-6600U / 8 GB RAM
# ─────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "═══════════════════════════════════════════"
echo "  Hope AI Agent — Debian Setup"
echo "═══════════════════════════════════════════"

# ── 1. System dependencies ──────────────────────────────────────────
echo ""
echo "[1/6] Checking system dependencies..."
if ! command -v python3 &>/dev/null; then
    echo "  Installing Python 3..."
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
fi
if ! command -v node &>/dev/null; then
    echo "  Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "  Python: $(python3 --version)"
echo "  Node:   $(node --version)"

# ── 2. Python virtual environment ──────────────────────────────────
echo ""
echo "[2/6] Setting up Python virtual environment..."
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "  Created venv/"
fi
source venv/bin/activate
pip install --upgrade pip -q

# ── 3. Python packages ─────────────────────────────────────────────
echo ""
echo "[3/6] Installing Python packages..."
pip install -r requirements.txt -q
echo "  Done. $(pip list --format=columns | wc -l) packages installed."

# ── 4. Node / Puppeteer ────────────────────────────────────────────
echo ""
echo "[4/6] Installing Puppeteer (Node.js)..."
if [ ! -d node_modules ]; then
    npm install --silent
fi
# Puppeteer on Debian needs these system libs for Chromium
echo "  Installing Chromium system dependencies..."
sudo apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libcups2 libxss1 2>/dev/null || true
echo "  Puppeteer ready."

# ── 5. Ollama local model ──────────────────────────────────────────
echo ""
echo "[5/6] Setting up local Ollama model..."
if ! command -v ollama &>/dev/null; then
    echo "  Ollama not found. Install from: https://ollama.ai"
    echo "  Then run: ollama pull llama3.2:3b"
else
    echo "  Ollama found: $(ollama --version 2>&1 | head -1)"
    # Check if preferred model is already pulled
    if ollama list 2>/dev/null | grep -q "llama3.2"; then
        echo "  ✓ llama3.2 model already available."
    else
        echo "  Pulling llama3.2:3b (2.0 GB download, fits in 8 GB RAM)..."
        echo "  This will take a few minutes on first run."
        ollama pull llama3.2:3b || echo "  ⚠ Pull failed — you can do this later: ollama pull llama3.2:3b"
    fi
fi

# ── 6. Environment file ───────────────────────────────────────────
echo ""
echo "[6/6] Environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo "  Created .env from .env.example"
    echo "  ⚠ Edit .env and add your API keys before starting Hope."
else
    echo "  ✓ .env already exists."
fi

# ── Done ───────────────────────────────────────────────────────────
mkdir -p workspace
echo ""
echo "═══════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys (optional: set NTFY_TOPIC for phone alerts)"
echo "    2. (Optional) Download Google OAuth credentials.json"
echo "    3. Start Hope Web App & API Server:"
echo "       source venv/bin/activate"
echo "       python app.py             # Modern Web App + PWA (http://localhost:8080)"
echo "       python hooks_server.py    # (Optional) Local GitHub webhook listener"
echo ""
echo "  Remote & Mobile Access (100% Free):"
echo "    Install Tailscale on Debian & phone, then open http://<tailscale-ip>:8080"
echo "    In Safari/Chrome, tap 'Add to Home Screen' for native full-screen PWA."
echo ""
echo "  Verify tools:  python -c \"import tools; print(len(tools.ALL_TOOLS), 'tools loaded')\""
echo "  Test browser:  node puppeteer_runner.js test"
echo "  Test local AI: python -c \"from brain.local_brain import LocalBrain; b = LocalBrain(); print('Model:', b.active_model)\""
echo "═══════════════════════════════════════════"

