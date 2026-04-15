# install_windows.ps1 — one-shot setup for claude_speak on Windows
#
# Run from inside the repo:    .\install_windows.ps1
# Or as a one-liner bootstrap (PowerShell):
#   irm https://raw.githubusercontent.com/SHerdilLodhi/whisper-cli/main/install_windows.ps1 | iex
#
# If blocked by execution policy, first run:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

$ErrorActionPreference = "Stop"

$RepoUrl    = "https://github.com/SHerdilLodhi/whisper-cli.git"
$InstallDir = "$HOME\whisper-cli"

Write-Host "=== claude_speak Windows installer ===" -ForegroundColor Cyan
Write-Host ""

# ── Python check ──────────────────────────────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found." -ForegroundColor Red
    Write-Host "Download Python 3.9+ from https://python.org"
    Write-Host "Check 'Add Python to PATH' during install, then re-run this script."
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "Using $pyVersion"

# ── Clone repo if running as one-liner (not already inside it) ────────────
if (-not (Test-Path "setup.py")) {
    Write-Host ""
    Write-Host "[0/4] Cloning repository..."
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "git not found. Install Git from https://git-scm.com then re-run." -ForegroundColor Red
        exit 1
    }
    git clone $RepoUrl $InstallDir
    Set-Location $InstallDir
}

# ── 1. ffmpeg ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[1/4] Checking ffmpeg..."
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "  ffmpeg already installed."
} else {
    Write-Host "  Installing ffmpeg via winget..."
    try {
        winget install --id Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements
        Write-Host "  ffmpeg installed."
        Write-Host "  NOTE: you may need to restart this terminal for ffmpeg to be on PATH."
    } catch {
        Write-Host "  winget install failed." -ForegroundColor Yellow
        Write-Host "  Download ffmpeg from https://ffmpeg.org/download.html"
        Write-Host "  Extract it and add the 'bin' folder to your PATH, then re-run."
        exit 1
    }
}

# ── 2. Virtual environment ────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Creating Python virtual environment..."
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# ── 3. Python packages ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 4. CLI entry point ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Installing claude_speak CLI..."
pip install -e . -q

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run:" -ForegroundColor Yellow
if (Test-Path $InstallDir) {
    Write-Host "  cd $InstallDir"
}
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  claude_speak"
Write-Host ""
Write-Host "On first run, Whisper downloads the 'base' model (~142 MB)." -ForegroundColor DarkGray
Write-Host "Text injection uses clipboard + Ctrl+V — keep your target window focused." -ForegroundColor DarkGray
