#!/usr/bin/env bash
# install.sh — one-shot setup for claude_speak
# Run: bash install.sh

set -e

echo "=== claude_speak installer ==="

# 1. System dependencies
echo ""
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    xdotool \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    python3-pip \
    python3-venv

# 2. Python virtual environment
echo ""
echo "[2/4] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 3. Python dependencies
echo ""
echo "[3/4] Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 4. Install claude_speak as a CLI command
echo ""
echo "[4/4] Installing claude_speak CLI..."
pip install -e . -q

echo ""
echo "=== Installation complete ==="
echo ""
echo "To activate the environment and run:"
echo "  source .venv/bin/activate"
echo "  claude_speak"
echo ""
echo "On first run, Whisper will download the 'base' model (~142MB)."
echo "Subsequent runs start in <2 seconds."
echo ""
echo "Optional: to use the 'small' model for better Urdu accuracy:"
echo "  mkdir -p ~/.config/claude_speak"
echo "  echo '{\"model\": \"small\"}' > ~/.config/claude_speak/config.json"
