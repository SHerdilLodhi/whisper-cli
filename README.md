# claude_speak

Voice-to-terminal: speak and the transcribed text appears at your cursor.

**Pipeline:** Microphone → Whisper STT → keyboard injection into the active window

- Trigger: double-tap **Ctrl** (toggle or push-to-talk)
- Offline — no cloud, no API key
- Supports English, Urdu, and any Whisper-supported language
- Cross-platform: Linux, macOS, Windows

---

## Install

### Linux

```bash
bash install.sh
source .venv/bin/activate
claude_speak
```

Requires: `xdotool` (X11) or `ydotool` (Wayland), `portaudio`, `ffmpeg` — the script installs these.

### macOS

```bash
bash install_mac.sh
source .venv/bin/activate
claude_speak
```

**Required permission (one-time setup):**
System Settings → Privacy & Security → Accessibility → click `+` → add your terminal app.
This single grant covers both the global hotkey listener and the auto-paste (Cmd+V injection).

### Windows

```powershell
.\install_windows.ps1
.\.venv\Scripts\Activate.ps1
claude_speak
```

Requires Python 3.9+ (from python.org). The script installs ffmpeg via `winget`.

---

## Usage

```
double-tap Ctrl   →  start recording
double-tap Ctrl   →  stop and transcribe  (toggle mode)
```

Transcribed text is injected into whatever window has focus when injection fires.

**macOS / Windows:** injection uses clipboard + paste shortcut (Cmd+V / Ctrl+V).
Your clipboard is temporarily overwritten during injection.

### CLI options

```
claude_speak --model small        # tiny | base | small | medium
claude_speak --mode push_to_talk  # hold to record, release to stop
claude_speak --edit               # review transcription before injecting
claude_speak --no-sound           # disable beep feedback
claude_speak --no-notify          # disable desktop notifications
```

---

## Configuration

| Platform | Config file |
|----------|-------------|
| Linux    | `~/.config/claude_speak/config.json` |
| macOS    | `~/Library/Application Support/claude_speak/config.json` |
| Windows  | `%APPDATA%\claude_speak\config.json` |

Example:

```json
{
  "model": "small",
  "language": "en",
  "trigger_mode": "push_to_talk",
  "strip_punctuation": true,
  "sound_feedback": true,
  "inject_delay": 0.4
}
```

---

## GUI (Linux only)

```bash
claude_speak_gui        # floating panel with animated waveform
claude_speak_gui &      # run in background, keep terminal free
```

The GUI requires GTK4 + Adwaita and is only supported on Linux.

---

## Calibrate noise threshold

```bash
python measure_noise.py
```

Measures your mic's background noise floor and prints a recommended `silence_threshold` for your config.

---

## Transcription history

| Platform | History file |
|----------|--------------|
| Linux    | `~/.local/share/claude_speak/history.jsonl` |
| macOS    | `~/Library/Application Support/claude_speak/history.jsonl` |
| Windows  | `%APPDATA%\claude_speak\history.jsonl` |

---

## Run as a background service (Linux only)

```bash
bash install_service.sh
journalctl --user -u claude_speak -f   # view logs
```
