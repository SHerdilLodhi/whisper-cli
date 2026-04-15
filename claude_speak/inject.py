"""
Keyboard injection engine — Wayland-first, X11 fallback.

Injection priority (Wayland):
  1. ydotool  — uses Linux uinput, works on all compositors including GNOME.
               Requires: sudo apt install ydotool
                         sudo usermod -aG input $USER  (then re-login)
  2. wtype    — uses zwp_virtual_keyboard_v1 Wayland protocol.
               Works on wlroots compositors (sway, hyprland) but NOT GNOME Mutter.
  3. clipboard fallback — copies text to clipboard via wl-copy, prompts user to Ctrl+V.
               Always works, zero setup. Less seamless but functional.

Injection (X11):
  xdotool type --window <id>  — targets specific window by ID.
  Install: sudo apt install xdotool
"""
import os
import subprocess
import time
import shutil
from typing import Optional


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _try_ydotool(text: str) -> bool:
    """Inject via ydotool (uinput). Works on GNOME Wayland."""
    if not shutil.which("ydotool"):
        return False
    try:
        subprocess.run(
            ["ydotool", "type", "--", text],
            check=True, timeout=30,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def _try_wtype(text: str) -> bool:
    """Inject via wtype. Works on wlroots compositors, NOT GNOME Mutter."""
    if not shutil.which("wtype"):
        return False
    try:
        subprocess.run(["wtype", text], check=True, timeout=30)
        return True
    except Exception:
        return False


def _clipboard_fallback(text: str) -> bool:
    """
    Copy text to Wayland clipboard, then auto-paste via ydotool if available.
    Falls back to manual Ctrl+V instruction.
    """
    if not shutil.which("wl-copy"):
        return False
    try:
        subprocess.run(["wl-copy", text], check=True, timeout=5)

        # Try auto-paste with ydotool (requires user in 'input' group)
        if shutil.which("ydotool"):
            time.sleep(0.3)
            result = subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                capture_output=True, stderr=subprocess.DEVNULL, timeout=5
            )
            if result.returncode == 0:
                return True  # Auto-pasted silently

        # Manual fallback
        print("📋 Text copied to clipboard.")
        print("   → Click your Claude terminal and press Ctrl+V to paste.")
        return True
    except Exception:
        return False


def check_injection_tool() -> bool:
    """Check that at least one injection method is available. Called at startup."""
    if _is_wayland():
        if shutil.which("ydotool"):
            print("[inject] Wayland detected — using ydotool (uinput)")
            return True
        if shutil.which("wtype"):
            print("[inject] Wayland detected — using wtype (may fail on GNOME)")
            return True
        if shutil.which("wl-copy"):
            print("[inject] Wayland detected — using clipboard fallback (install ydotool for auto-typing)")
            print("[inject]   sudo apt install ydotool && sudo usermod -aG input $USER")
            return True
        print("[inject] No injection tool found. Install one of:")
        print("[inject]   sudo apt install ydotool wl-clipboard")
        return False
    else:
        if shutil.which("xdotool"):
            print("[inject] X11 detected — using xdotool")
            return True
        print("[inject] xdotool not found. Install with: sudo apt install xdotool")
        return False


def get_active_window() -> Optional[str]:
    """X11 only — return active window ID. Wayland doesn't need this."""
    if _is_wayland():
        return None
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, check=True, timeout=2,
        )
        window_id = result.stdout.strip()
        return window_id if window_id else None
    except Exception as e:
        print(f"[inject] Could not get active window: {e}")
        return None


def inject_text(text: str, window_id: Optional[str], delay_before: float = 0.5) -> bool:
    """
    Inject text as keystrokes. Tries multiple methods in order of preference.
    Returns True if text was injected (or copied to clipboard).
    """
    if not text:
        print("[inject] Nothing to inject (empty text)")
        return False

    time.sleep(delay_before)

    if _is_wayland():
        if _try_ydotool(text):
            return True

        if _try_wtype(text):
            return True
        if _clipboard_fallback(text):
            return True  # Partial success — user must paste manually
        print("[inject] All injection methods failed.")
        print("[inject] Install ydotool: sudo apt install ydotool && sudo usermod -aG input $USER")
        return False
    else:
        try:
            cmd = ["xdotool", "type", "--clearmodifiers", "--delay", "20"]
            if window_id:
                cmd += ["--window", window_id]
            cmd.append(text)
            subprocess.run(cmd, check=True, timeout=30)
            return True
        except Exception as e:
            print(f"[inject] xdotool failed: {e}")
            return False
