"""
Transcription history logger for claude_speak.

Appends a JSON line per transcription to a JSONL history file.
"""
import os
import json
import time

HISTORY_PATH = os.path.expanduser("~/.local/share/claude_speak/history.jsonl")


def log(text: str, duration: float, transcribe_time: float) -> None:
    """
    Append a JSON line to the history file.

    Fields written:
      timestamp      — ISO-8601 UTC timestamp
      text           — transcribed text
      duration       — audio recording length in seconds
      transcribe_time — time spent on transcription in seconds
    """
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "text": text,
            "duration": round(duration, 3),
            "transcribe_time": round(transcribe_time, 3),
        }
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[history] Could not write to history: {e}")
