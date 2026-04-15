"""
claude_speak — speak into your terminal, text appears at the cursor.
"""
import os
import sys
import time
import threading
import warnings
import argparse

# Suppress torch/CUDA warnings — not relevant on CPU-only setups
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

from .config import Config
from .audio import AudioCapture, check_microphone
from .transcribe import load_model, transcribe
from .transcribe import strip_punctuation as _strip_punctuation
from .inject import check_injection_tool, get_active_window, inject_text
from .hotkey import HotkeyListener
from .notify import beep, notify
from .shortcuts import check_shortcut, run_shortcut
from . import history

_early_stop = threading.Event()
_is_recording = False
_is_editing = False

W = 42  # Banner width


# ---------------------------------------------------------------------------
# readline pre-fill helper
# ---------------------------------------------------------------------------

def _input_with_prefill(prompt: str, text: str) -> str:
    """Show an input prompt pre-filled with *text* so the user can edit it."""
    try:
        import readline

        def hook():
            readline.insert_text(text)
            readline.redisplay()

        readline.set_pre_input_hook(hook)
        try:
            return input(prompt)
        finally:
            readline.set_pre_input_hook()
    except ImportError:
        # readline not available — fall back to plain input
        print(f"  [edit] readline unavailable; using text as-is: {text!r}")
        return text


# ---------------------------------------------------------------------------
# Banner / ready line
# ---------------------------------------------------------------------------

def _banner(cfg: Config, mic: str, injection: str):
    mode_label = "push-to-talk" if cfg.trigger_mode == "push_to_talk" else "toggle"
    line = "─" * W
    print(f"\n┌{line}┐")
    print(f"│{'  claude_speak':^{W}}│")
    print(f"├{line}┤")
    print(f"│  {'Hotkey':<12}  Ctrl + Shift{'':<{W - 28}}│")
    print(f"│  {'Mode':<12}  {mode_label:<{W - 18}}│")
    print(f"│  {'Microphone':<12}  {mic:<{W - 18}}│")
    print(f"│  {'Model':<12}  Whisper {cfg.model:<{W - 24}}│")
    print(f"│  {'Injection':<12}  {injection:<{W - 18}}│")
    print(f"└{line}┘")


def _ready(cfg: Config):
    if cfg.trigger_mode == "push_to_talk":
        print("\n  ● Ready — double-tap Ctrl to start · double-tap again to stop\n")
    else:
        print("\n  ● Ready — double-tap Ctrl to start / stop\n")


# ---------------------------------------------------------------------------
# Recording pipeline
# ---------------------------------------------------------------------------

def run_pipeline(cfg: Config, audio_capture: AudioCapture) -> None:
    global _is_recording, _is_editing
    _early_stop.clear()
    _is_recording = True

    window_id = get_active_window()

    # Beep on start
    if cfg.sound_feedback:
        beep(freq=880, duration=0.08, volume=0.3)

    # Live timer thread
    _timer_stop = threading.Event()

    def _show_timer():
        t = 0
        while not _timer_stop.is_set():
            sys.stdout.write(f"  ◉ Recording...  {t}s  (Ctrl+Shift to stop)\r")
            sys.stdout.flush()
            time.sleep(1)
            t += 1

    timer_thread = threading.Thread(target=_show_timer, daemon=True)
    timer_thread.start()

    audio = audio_capture.record(early_stop_event=_early_stop)
    _is_recording = False
    _timer_stop.set()

    sys.stdout.write(" " * 55 + "\r")
    sys.stdout.flush()

    # Beep on stop
    if cfg.sound_feedback:
        beep(freq=660, duration=0.08, volume=0.3)

    if audio is None:
        print("  ✗  No audio captured — try again\n")
        _ready(cfg)
        return

    duration = len(audio) / cfg.sample_rate
    threshold = getattr(audio_capture, '_threshold', '?')
    if isinstance(threshold, float):
        print(f"  ◉ Recorded {duration:.1f}s  (noise threshold: {threshold:.4f})")
    else:
        print(f"  ◉ Recorded {duration:.1f}s")

    sys.stdout.write("  ◌ Transcribing...\r")
    sys.stdout.flush()

    t_start = time.monotonic()
    text = transcribe(audio, cfg.sample_rate, cfg.language)
    t_elapsed = time.monotonic() - t_start

    sys.stdout.write(" " * 50 + "\r")
    sys.stdout.flush()

    if not text:
        print("  ✗  No speech detected — try again\n")
        _ready(cfg)
        return

    # Strip trailing punctuation
    if cfg.strip_punctuation:
        text = _strip_punctuation(text)

    # Check shortcuts — if matched, run command and skip injection
    if cfg.shortcuts:
        command = check_shortcut(text, cfg.shortcuts)
        if command is not None:
            preview = text if len(text) <= 60 else text[:57] + "..."
            print(f"  ⚡ Shortcut matched: \"{preview}\" → {command}")
            run_shortcut(command)
            _ready(cfg)
            return

    # Edit mode — let user tweak the transcription before injecting
    if cfg.edit_mode:
        _is_editing = True
        try:
            text = _input_with_prefill("  ✎ Edit: ", text)
            text = text.strip()
        finally:
            _is_editing = False

    if not text:
        print("  ✗  Empty text after edit — skipping injection\n")
        _ready(cfg)
        return

    # Truncate long text for display
    preview = text if len(text) <= 60 else text[:57] + "..."
    print(f"  ✓  \"{preview}\"  ({t_elapsed:.1f}s)")

    # Desktop notification
    if cfg.notifications:
        notify("claude_speak", text)

    # Inject into active window
    inject_text(text, window_id, delay_before=cfg.inject_delay)

    # Log to history
    if cfg.history_enabled:
        history.log(text, duration=duration, transcribe_time=t_elapsed)

    _ready(cfg)


# ---------------------------------------------------------------------------
# Hotkey callbacks
# ---------------------------------------------------------------------------

def _on_enter():
    if _is_recording:
        _early_stop.set()


def _make_on_hotkey(cfg: Config, audio_capture: AudioCapture):
    def on_hotkey():
        if _is_editing:
            return  # Don't start a new recording while the user is editing
        if cfg.trigger_mode == "push_to_talk":
            # push_to_talk: on_stop will set _early_stop when keys are released
            threading.Thread(
                target=run_pipeline, args=(cfg, audio_capture), daemon=True
            ).start()
        else:
            # toggle mode
            if _is_recording:
                _early_stop.set()  # Stop current recording
            else:
                threading.Thread(
                    target=run_pipeline, args=(cfg, audio_capture), daemon=True
                ).start()

    return on_hotkey


def _make_on_stop():
    """push_to_talk: called when Ctrl or Shift is released."""
    def on_stop():
        _early_stop.set()

    return on_stop


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # --- Parse command-line arguments ---
    parser = argparse.ArgumentParser(
        prog="claude_speak",
        description="Voice-to-terminal: speak and the text appears at your cursor.",
    )
    parser.add_argument(
        "--model",
        choices=["tiny", "base", "small", "medium"],
        default=None,
        help="Whisper model to use (overrides config)",
    )
    parser.add_argument(
        "--mode",
        choices=["toggle", "push_to_talk"],
        default=None,
        help="Trigger mode: toggle or push_to_talk (overrides config)",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        default=False,
        help="Enable edit mode: show editable prompt before injecting",
    )
    parser.add_argument(
        "--no-sound",
        action="store_true",
        default=False,
        help="Disable sound feedback (beeps)",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        default=False,
        help="Disable desktop notifications",
    )
    args = parser.parse_args()

    cfg = Config.load()

    # Apply CLI overrides
    if args.model is not None:
        cfg.model = args.model
    if args.mode is not None:
        cfg.trigger_mode = args.mode
    if args.edit:
        cfg.edit_mode = True
    if args.no_sound:
        cfg.sound_feedback = False
    if args.no_notify:
        cfg.notifications = False

    # --- Collect status info quietly before printing banner ---
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mic_ok, mic_name = check_microphone()
        inject_ok = check_injection_tool()

    # Extract injection method label from captured output
    captured = buf.getvalue()
    injection_method = "clipboard"
    for line in captured.splitlines():
        if "using ydotool" in line:
            injection_method = "ydotool"
        elif "using wtype" in line:
            injection_method = "wtype"
        elif "using xdotool" in line:
            injection_method = "xdotool"
        elif "clipboard" in line:
            injection_method = "clipboard (install ydotool)"

    if not mic_ok or not inject_ok:
        print(captured)
        sys.exit(1)

    # --- Load model silently ---
    sys.stdout.write("  Loading model...\r")
    sys.stdout.flush()

    import contextlib as _cl
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stderr(devnull):
            load_model(cfg.model)

    sys.stdout.write(" " * 30 + "\r")
    sys.stdout.flush()

    _banner(cfg, mic_name, injection_method)

    audio_capture = AudioCapture(cfg)

    on_hotkey = _make_on_hotkey(cfg, audio_capture)
    on_stop   = _make_on_stop() if cfg.trigger_mode == "push_to_talk" else None

    listener = HotkeyListener(
        hotkey=cfg.hotkey,
        on_trigger=on_hotkey,
        on_enter=_on_enter,
        mode=cfg.trigger_mode,
        on_stop=on_stop,
    )
    listener.start()

    _ready(cfg)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Goodbye.\n")
        listener.stop()
        sys.exit(0)
