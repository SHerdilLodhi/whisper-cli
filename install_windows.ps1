# install_windows.ps1 — one-shot setup for claude_speak on Windows
# Run in PowerShell: .\install_windows.ps1
# If blocked by execution policy, first run:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

$ErrorActionPreference = "Stop"

Write-Host "=== claude_speak Windows installer ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python check ───────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found." -ForegroundColor Red
    Write-Host "Download and install Python 3.9+ from https://python.org"
    Write-Host "Make sure to check 'Add Python to PATH' during install."
    exit 1
}

$pyVersion = python --version 2>&1
Write-Host "Using $pyVersion"

# ── 2. ffmpeg ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[1/4] Checking ffmpeg..."
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "  ffmpeg already installed."
} else {
    Write-Host "  Installing ffmpeg via winget..."
    try {
        winget install --id Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements
        Write-Host "  ffmpeg installed. You may need to restart PowerShell for PATH to update."
    } catch {
        Write-Host "  winget failed. Download ffmpeg manually from https://ffmpeg.org/download.html" -ForegroundColor Yellow
        Write-Host "  Extract it and add the 'bin' folder to your PATH, then re-run this script."
        exit 1
    }
}

# ── 3. Virtual environment ────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Creating Python virtual environment..."
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# ── 4. Python packages ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 5. CLI entry point ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Installing claude_speak CLI..."
pip install -e . -q

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  claude_speak"
Write-Host ""
Write-Host "On first run, Whisper downloads the 'base' model (~142 MB)."
Write-Host "Subsequent starts are instant."
Write-Host ""
Write-Host "Optional: use the 'small' model for better accuracy:"
Write-Host "  New-Item -Path `$env:APPDATA\claude_speak -ItemType Directory -Force"
Write-Host "  Set-Content `$env:APPDATA\claude_speak\config.json '{`"model`": `"small`"}'"
Write-Host ""
Write-Host "Note: text injection uses clipboard + Ctrl+V." -ForegroundColor DarkGray
Write-Host "Make sure your target window has focus before the transcription completes." -ForegroundColor DarkGray
