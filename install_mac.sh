#!/usr/bin/env bash
# install_mac.sh — one-shot setup for claude_speak on macOS
#
# Run from inside the repo:    bash install_mac.sh
# Or as a one-liner bootstrap: bash <(curl -fsSL https://raw.githubusercontent.com/SHerdilLodhi/whisper-cli/main/install_mac.sh)

set -e

REPO_URL="https://github.com/SHerdilLodhi/whisper-cli.git"
INSTALL_DIR="$HOME/whisper-cli"

echo "=== claude_speak macOS installer ==="
echo ""

# ── Homebrew check ─────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Install it from https://brew.sh then re-run."
    exit 1
fi

# ── Clone repo if running as one-liner (not already inside it) ─────────────
if [ ! -f "setup.py" ]; then
    echo "[0/4] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── 1. System dependencies ─────────────────────────────────────────────────
echo "[1/4] Installing system packages (portaudio, ffmpeg)..."
brew install portaudio ffmpeg

# ── 2. Python virtual environment ─────────────────────────────────────────
echo ""
echo "[2/4] Creating Python virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# ── 3. Python packages ────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 4. CLI entry point ────────────────────────────────────────────────────
echo ""
echo "[4/4] Installing claude_speak CLI..."
pip install -e . -q

echo ""
echo "=== Installation complete ==="
echo ""
echo "IMPORTANT — grant Accessibility permission before first run:"
echo "  System Settings → Privacy & Security → Accessibility"
echo "  Click [+] and add your terminal app (Terminal, iTerm2, Warp, etc.)"
echo "  This covers both the global hotkey AND auto-paste (Cmd+V)."
echo ""
if [ -d "$INSTALL_DIR" ]; then
    echo "To run:"
    echo "  cd $INSTALL_DIR"
    echo "  source .venv/bin/activate"
    echo "  claude_speak"
else
    echo "To run:"
    echo "  source .venv/bin/activate"
    echo "  claude_speak"
fi
echo ""
echo "On first run, Whisper downloads the 'base' model (~142 MB)."
