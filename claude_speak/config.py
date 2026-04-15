"""
Configuration for claude_speak.
Loaded from ~/.config/claude_speak/config.json, with sane defaults.
"""
import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_PATH = os.path.expanduser("~/.config/claude_speak/config.json")

@dataclass
class Config:
    # Whisper model to use: tiny | base | small | medium | large
    # base = 142MB, ~1-3s transcription, good multilingual (English + Urdu)
    # small = 244MB, ~2-5s, better Urdu accuracy — change if Urdu accuracy matters more than speed
    model: str = "base"

    # Audio recording
    sample_rate: int = 16000        # Hz — Whisper expects 16kHz
    channels: int = 1               # Mono
    blocksize: int = 1024           # Audio callback block size in frames

    # Silence detection (stops recording automatically)
    silence_threshold: float = 0.05   # RMS amplitude — lower = more sensitive
    silence_duration: float = 0.8     # Seconds of silence before stopping
    min_speech_duration: float = 0.4  # Minimum seconds of audio to attempt transcription

    # Hard cap on recording length
    max_duration: float = 15.0

    # Delay before injecting text (lets the terminal settle after focus)
    inject_delay: float = 0.3

    # Global hotkey combo (pynput format)
    # Default: Ctrl+Space. Change to e.g. "<ctrl>+<shift>+<space>" if IBus intercepts it
    hotkey: str = "<ctrl>+<space>"

    # Whisper language hint. None = auto-detect (handles English + Urdu)
    # Set to "ur" if you only speak Urdu, "en" for English-only (faster)
    language: Optional[str] = None

    # Trigger mode: "toggle" (press once to start, press again to stop)
    # or "push_to_talk" (hold to record, release to stop)
    trigger_mode: str = "toggle"

    # Play a short beep when recording starts/stops
    sound_feedback: bool = True

    # Send desktop notification with transcribed text
    notifications: bool = True

    # Remove trailing punctuation (. , ; ! ?) from injected text
    strip_punctuation: bool = True

    # Show editable prompt before injecting text
    edit_mode: bool = False

    # Log transcriptions to history file
    history_enabled: bool = True

    # Phrase→command shortcut mapping
    # e.g. {"open browser": "xdg-open https://google.com"}
    shortcuts: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, falling back to defaults for missing keys."""
        if not os.path.exists(CONFIG_PATH):
            return cls()
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            valid_keys = cls.__dataclass_fields__.keys()
            return cls(**{k: v for k, v in data.items() if k in valid_keys})
        except Exception as e:
            print(f"[config] Warning: could not load config ({e}), using defaults")
            return cls()

    def save(self):
        """Persist current config to disk."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(asdict(self), f, indent=2)
        print(f"[config] Saved to {CONFIG_PATH}")
