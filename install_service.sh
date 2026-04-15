#!/usr/bin/env bash
# install_service.sh — Install claude_speak as a systemd user service
# Run once after initial setup: bash install_service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/claude_speak.service"

echo "==> Installing udev rule for uinput..."
python3 -c "
import subprocess
rule = 'KERNEL==\"uinput\", GROUP=\"input\", MODE=\"0660\"'
subprocess.run(['sudo', 'tee', '/etc/udev/rules.d/60-uinput.rules'], input=rule.encode(), check=True)
subprocess.run(['sudo', 'udevadm', 'trigger'], check=True)
print('udev rule installed')
"

echo ""
echo "==> Creating systemd user service at $SERVICE_FILE..."
mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=claude_speak - voice to terminal
After=graphical-session.target

[Service]
Type=simple
ExecStart=/home/sherdil-lodhi/Documents/PR/CLI Speak Command Tool/.venv/bin/python -m claude_speak.main
WorkingDirectory=/home/sherdil-lodhi/Documents/PR/CLI Speak Command Tool
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
Environment=XDG_RUNTIME_DIR=/run/user/1000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

echo "Service file written."

echo ""
echo "==> Enabling and starting claude_speak service..."
systemctl --user daemon-reload
systemctl --user enable claude_speak
systemctl --user start claude_speak

echo ""
echo "==> Status:"
systemctl --user status claude_speak --no-pager || true

echo ""
echo "Done. claude_speak is now running as a systemd user service."
echo "  View logs:   journalctl --user -u claude_speak -f"
echo "  Stop:        systemctl --user stop claude_speak"
echo "  Disable:     systemctl --user disable claude_speak"
