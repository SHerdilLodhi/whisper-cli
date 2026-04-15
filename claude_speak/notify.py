"""
Audio and desktop notification helpers for claude_speak.

beep()   — plays a short sine wave tone via sounddevice (non-blocking, all platforms)
notify() — sends a desktop notification (platform-adaptive)

  Linux:   notify-send
  macOS:   osascript display notification (no extra deps)
  Windows: plyer if installed, then PowerShell balloon tip fallback
"""
import sys
import subprocess
import threading


def beep(freq: float = 880, duration: float = 0.08, volume: float = 0.3) -> None:
    """
    Play a sine wave beep using sounddevice (non-blocking).
    Uses a daemon thread so it never blocks the caller.
    Adds fade-in/out to avoid click artifacts.
    """
    def _play():
        try:
            import numpy as np
            import sounddevice as sd

            sample_rate = 44100
            t    = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            wave = (volume * np.sin(2 * np.pi * freq * t)).astype(np.float32)

            fade_len = max(1, int(len(wave) * 0.10))
            wave[:fade_len]  *= np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
            wave[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)

            sd.play(wave, samplerate=sample_rate)
            sd.wait()
        except Exception:
            pass  # Beep is non-critical — never crash on audio errors

    threading.Thread(target=_play, daemon=True).start()


# ── platform notification implementations ─────────────────────────────────────

def _notify_linux(title: str, body: str) -> None:
    """notify-send — standard on GNOME, KDE, etc."""
    cmd = ["notify-send", "-t", "3000", "-a", "claude_speak", title]
    if body:
        cmd.append(body)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _notify_macos(title: str, body: str) -> None:
    """
    osascript display notification — always available on macOS, no deps.
    Double-quotes in title/body are escaped to prevent AppleScript injection.
    """
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_body  = body.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{safe_body}" with title "{safe_title}"'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _notify_windows(title: str, body: str) -> None:
    """
    Windows notification: tries plyer first (optional dep), then falls back
    to a PowerShell balloon tip (no extra packages needed).
    """
    # plyer is the cleanest cross-platform option
    try:
        from plyer import notification as _n
        _n.notify(title=title, message=body, app_name="claude_speak", timeout=3)
        return
    except ImportError:
        pass
    except Exception:
        pass

    # PowerShell balloon tip — zero extra dependencies
    try:
        # Escape single quotes for PowerShell string safety
        safe_title = title.replace("'", "''")
        safe_body  = body.replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.Visible = $true; "
            f"$n.ShowBalloonTip(3000, '{safe_title}', '{safe_body}', "
            "[System.Windows.Forms.ToolTipIcon]::None); "
            "Start-Sleep -Milliseconds 3500; $n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Notification is non-critical — never crash


# ── Public API ────────────────────────────────────────────────────────────────

def notify(title: str, body: str = "") -> None:
    """Send a desktop notification. All errors are suppressed silently."""
    try:
        if sys.platform == "darwin":
            _notify_macos(title, body)
        elif sys.platform == "win32":
            _notify_windows(title, body)
        else:
            _notify_linux(title, body)
    except Exception:
        pass
