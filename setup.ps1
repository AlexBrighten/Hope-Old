# ─────────────────────────────────────────────────────────────────────
#  setup.ps1 — Full setup script for Hope AI Agent on Windows
# ─────────────────────────────────────────────────────────────────────

Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Hope AI Agent — Windows Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan

# ── 1. Check Python & Node ──────────────────────────────────────────
Write-Host "`n[1/5] Checking runtime environments..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    Write-Host "  ✓ Python: $(python --version)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Python not found in PATH" -ForegroundColor Red
}

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "  ✓ Node: $(node --version)" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Node.js not found in PATH" -ForegroundColor Red
}

# ── 2. Install Python Dependencies ──────────────────────────────────
Write-Host "`n[2/5] Installing Python packages from requirements.txt..." -ForegroundColor Yellow
python -m pip install -r requirements.txt --quiet
Write-Host "  ✓ Python dependencies installed." -ForegroundColor Green

# ── 3. Install Node / Puppeteer Dependencies ────────────────────────
Write-Host "`n[3/5] Installing Puppeteer (Node.js)..." -ForegroundColor Yellow
if (!(Test-Path "node_modules")) {
    npm install --silent
}
Write-Host "  ✓ Puppeteer dependencies installed." -ForegroundColor Green

# ── 4. Setup .env file ──────────────────────────────────────────────
Write-Host "`n[4/5] Checking environment configuration..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ Created .env from .env.example" -ForegroundColor Green
    Write-Host "  ⚠ Please edit .env with your GEMINI_API_KEY and other tokens." -ForegroundColor Yellow
} else {
    Write-Host "  ✓ .env already exists." -ForegroundColor Green
}

# ── 5. Verify Tool Suite ────────────────────────────────────────────
Write-Host "`n[5/5] Verifying tool registry..." -ForegroundColor Yellow
python -c "import tools; print(f'  ✓ {len(tools.ALL_TOOLS)} tools loaded successfully!')"

Write-Host "`n═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Cyan
Write-Host "  Run: python agent.py       (Web UI)" -ForegroundColor White
Write-Host "  Run: python telegram_bot.py (Telegram Bot)" -ForegroundColor White
Write-Host "  Run: python hooks_server.py (Webhook Server)" -ForegroundColor White
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan

