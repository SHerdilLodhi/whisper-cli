#!/usr/bin/env bash
# install.sh — one-shot setup for claude_speak on Linux
#
# Run from inside the repo:    bash install.sh
# Or as a one-liner bootstrap: bash <(curl -fsSL https://raw.githubusercontent.com/SHerdilLodhi/whisper-cli/main/install.sh)

set -e

REPO_URL="https://github.com/SHerdilLodhi/whisper-cli.git"
INSTALL_DIR="$HOME/whisper-cli"

echo "=== claude_speak installer ==="

# ── Clone repo if running as one-liner (not already inside it) ─────────────
if [ ! -f "setup.py" ]; then
    echo "[0/4] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── 1. System dependencies ─────────────────────────────────────────────────
echo ""
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    xdotool \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    python3-pip \
    python3-venv \
    git

# ── 2. Python virtual environment ─────────────────────────────────────────
echo ""
echo "[2/4] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# ── 3. Python dependencies ─────────────────────────────────────────────────
echo ""
echo "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ── 4. Install claude_speak as a CLI command ───────────────────────────────
echo ""
echo "[4/4] Installing claude_speak CLI..."
pip install -e . -q

echo ""
echo "=== Installation complete ==="
echo ""
if [ -d "$INSTALL_DIR" ]; then
    echo "To run:"
    echo "  cd $INSTALL_DIR && source .venv/bin/activate && claude_speak"
else
    echo "To run:"
    echo "  source .venv/bin/activate && claude_speak"
fi
echo ""
echo "On first run, Whisper downloads the 'base' model (~142 MB)."
