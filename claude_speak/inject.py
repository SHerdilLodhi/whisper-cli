"""
Keyboard injection engine.

Platform dispatch:
  Linux   — Wayland: ydotool → wtype → clipboard fallback
             X11: xdotool
  macOS   — clipboard (pyperclip) + Cmd+V via osascript
  Windows — clipboard (pyperclip) + Ctrl+V via ctypes keybd_event

On macOS/Windows the clipboard approach handles all Unicode text (including
Urdu) correctly. The inject_delay gives the target window time to regain
focus before the paste is sent.

macOS note: osascript uses System Events to simulate Cmd+V, which requires
the same Accessibility permission as the hotkey listener. One grant covers both.
"""
import os
import sys
import subprocess
import time
import shutil
from typing import Optional


# ── macOS injection ───────────────────────────────────────────────────────────

def _mac_inject(text: str) -> bool:
    """Copy text to clipboard via pyperclip, then paste with osascript Cmd+V."""
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        print("[inject] pyperclip not installed. Run: pip install pyperclip")
        return False
    except Exception as e:
        print(f"[inject] Clipboard write failed: {e}")
        return False

    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "v" using command down'],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        # osascript failed — clipboard is still set; prompt manual paste
        print("Clipboard ready. Press Cmd+V to paste.")
        return True


def _mac_check_injection() -> bool:
    try:
        import pyperclip  # noqa: F401
        print("[inject] macOS detected — clipboard + Cmd+V (osascript)")
        print("[inject] Requires Accessibility permission (same grant as hotkey listener)")
        return True
    except ImportError:
        print("[inject] pyperclip not installed. Run: pip install pyperclip")
        return False


# ── Windows injection ─────────────────────────────────────────────────────────

def _windows_ctrl_v() -> None:
    """Simulate Ctrl+V via Windows keybd_event (ctypes — no extra deps)."""
    import ctypes
    user32          = ctypes.windll.user32
    VK_CONTROL      = 0x11
    VK_V            = 0x56
    KEYEVENTF_KEYUP = 0x0002

    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V,       0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_V,       0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def _windows_inject(text: str) -> bool:
    """Copy text to clipboard via pyperclip, then paste with Ctrl+V."""
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        print("[inject] pyperclip not installed. Run: pip install pyperclip")
        return False
    except Exception as e:
        print(f"[inject] Clipboard write failed: {e}")
        return False

    try:
        _windows_ctrl_v()
        return True
    except Exception as e:
        print(f"[inject] Ctrl+V simulation failed: {e}")
        print("Clipboard ready. Press Ctrl+V to paste.")
        return True  # Clipboard is set — partial success


def _windows_check_injection() -> bool:
    try:
        import pyperclip  # noqa: F401
        print("[inject] Windows detected — clipboard + Ctrl+V (ctypes)")
        return True
    except ImportError:
        print("[inject] pyperclip not installed. Run: pip install pyperclip")
        return False


# ── Linux helpers (unchanged) ─────────────────────────────────────────────────

def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _try_ydotool(text: str) -> bool:
    if not shutil.which("ydotool"):
        return False
    try:
        subprocess.run(
            ["ydotool", "type", "--", text],
            check=True, timeout=30,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _try_wtype(text: str) -> bool:
    if not shutil.which("wtype"):
        return False
    try:
        subprocess.run(["wtype", text], check=True, timeout=30)
        return True
    except Exception:
        return False


def _linux_clipboard_fallback(text: str) -> bool:
    if not shutil.which("wl-copy"):
        return False
    try:
        subprocess.run(["wl-copy", text], check=True, timeout=5)
        if shutil.which("ydotool"):
            time.sleep(0.3)
            result = subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                capture_output=True, stderr=subprocess.DEVNULL, timeout=5,
            )
            if result.returncode == 0:
                return True
        print("Clipboard ready. Press Ctrl+V to paste.")
        return True
    except Exception:
        return False


def _linux_check_injection() -> bool:
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


def _linux_inject(text: str, window_id: Optional[str]) -> bool:
    if _is_wayland():
        if _try_ydotool(text):
            return True
        if _try_wtype(text):
            return True
        if _linux_clipboard_fallback(text):
            return True
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


# ── Public API ────────────────────────────────────────────────────────────────

def check_injection_tool() -> bool:
    """Check that at least one injection method is available. Called at startup."""
    if sys.platform == "darwin":
        return _mac_check_injection()
    if sys.platform == "win32":
        return _windows_check_injection()
    return _linux_check_injection()


def get_active_window() -> Optional[str]:
    """
    Return the active window ID for xdotool targeting (X11 Linux only).
    Returns None on Wayland, macOS, and Windows — not needed for those paths.
    """
    if sys.platform != "linux" or _is_wayland():
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
    Inject text into the active window.

    Waits delay_before seconds first so the target window can regain focus
    after the hotkey. On macOS/Windows this uses clipboard + paste shortcut,
    which handles all Unicode (including Urdu) correctly.

    Returns True if text was injected or copied to clipboard.
    """
    if not text:
        print("[inject] Nothing to inject (empty text)")
        return False

    time.sleep(delay_before)

    if sys.platform == "darwin":
        return _mac_inject(text)
    if sys.platform == "win32":
        return _windows_inject(text)
    return _linux_inject(text, window_id)
