#!/usr/bin/env bash
# install_mac.sh — one-shot setup for claude_speak on macOS
# Run: bash install_mac.sh

set -e

echo "=== claude_speak macOS installer ==="
echo ""

# ── 1. Homebrew check ──────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found."
    echo "Install it from https://brew.sh then re-run this script."
    exit 1
fi

# ── 2. System dependencies ─────────────────────────────────────────────────
echo "[1/4] Installing system packages (portaudio, ffmpeg)..."
brew install portaudio ffmpeg

# ── 3. Python virtual environment ─────────────────────────────────────────
echo ""
echo "[2/4] Creating Python virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# ── 4. Python packages ────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 5. CLI entry point ────────────────────────────────────────────────────
echo ""
echo "[4/4] Installing claude_speak CLI..."
pip install -e . -q

echo ""
echo "=== Installation complete ==="
echo ""
echo "IMPORTANT — grant Accessibility permission before first run:"
echo "  System Settings → Privacy & Security → Accessibility"
echo "  Click [+] and add your terminal app (Terminal, iTerm2, Warp, etc.)"
echo "  This is needed for the global hotkey AND for auto-paste (Cmd+V)."
echo ""
echo "To run:"
echo "  source .venv/bin/activate"
echo "  claude_speak"
echo ""
echo "On first run, Whisper downloads the 'base' model (~142 MB)."
echo "Subsequent starts are instant."
echo ""
echo "Optional: use the 'small' model for better accuracy:"
echo "  mkdir -p ~/Library/Application\ Support/claude_speak"
echo "  echo '{\"model\": \"small\"}' > ~/Library/Application\ Support/claude_speak/config.json"
