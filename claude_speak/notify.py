"""
Audio and desktop notification helpers for claude_speak.

beep()   — plays a short sine wave tone via sounddevice (non-blocking)
notify() — sends a desktop notification via notify-send
"""
import subprocess
import threading
from typing import Optional


def beep(freq: float = 880, duration: float = 0.08, volume: float = 0.3) -> None:
    """
    Play a sine wave beep using sounddevice (non-blocking).
    Uses a separate thread so it does not block the caller.
    Adds a short fade-in and fade-out to avoid clicks.
    """
    def _play():
        try:
            import numpy as np
            import sounddevice as sd

            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            wave = volume * np.sin(2 * np.pi * freq * t).astype(np.float32)

            # Fade in/out: 10% of duration on each end, minimum 1 sample
            fade_len = max(1, int(len(wave) * 0.10))
            fade_in  = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
            wave[:fade_len]  *= fade_in
            wave[-fade_len:] *= fade_out

            sd.play(wave, samplerate=sample_rate)
            sd.wait()
        except Exception:
            pass  # Beep is non-critical — never crash on audio errors

    threading.Thread(target=_play, daemon=True).start()


def notify(title: str, body: str = "") -> None:
    """
    Send a desktop notification via notify-send.
    Suppresses errors silently if notify-send is not available.
    """
    try:
        cmd = ["notify-send", "-t", "3000", "-a", "claude_speak", title]
        if body:
            cmd.append(body)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # Notification is non-critical
