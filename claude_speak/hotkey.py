"""
Global hotkey listener — double-tap Ctrl to trigger recording.

Platform dispatch:
  Linux   — evdev reads /dev/input/event* directly.
             Works on both X11 and Wayland. User must be in the 'input' group.
  macOS   — pynput Listener.
             Requires: System Settings → Privacy & Security → Accessibility
             → add your terminal app (Terminal, iTerm2, etc.).
  Windows — pynput Listener. No extra OS permissions needed.

Trigger: two clean Ctrl taps (down+up) within 500ms, with no other key pressed
between them. Same state machine on all platforms.
"""
import sys
import threading
import time
from typing import Callable, Optional

# ── evdev (Linux only) ────────────────────────────────────────────────────────

try:
    import evdev
    from evdev import ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False

if _EVDEV_AVAILABLE:
    _CTRL_KEYS = {ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL}


def _find_keyboards():
    if not _EVDEV_AVAILABLE:
        return []
    keyboards = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps and ecodes.KEY_A in caps.get(ecodes.EV_KEY, []):
                keyboards.append(dev)
        except Exception:
            pass
    return keyboards


class _EvdevHotkeyListener:
    """Linux hotkey listener using evdev (original implementation)."""

    def __init__(self, hotkey: str, on_trigger: Callable[[], None],
                 on_enter: Optional[Callable[[], None]] = None,
                 mode: str = "toggle",
                 on_stop: Optional[Callable[[], None]] = None):
        self._hotkey     = hotkey
        self._on_trigger = on_trigger
        self._on_enter   = on_enter
        self._mode       = mode
        self._on_stop    = on_stop
        self._threads: list[threading.Thread] = []
        self._running    = False
        self._lock       = threading.Lock()
        self._active     = False

    def start(self) -> bool:
        if not _EVDEV_AVAILABLE:
            print("[hotkey] evdev not installed. Run: pip install evdev")
            return False

        keyboards = _find_keyboards()
        if not keyboards:
            print("[hotkey] No keyboard devices found in /dev/input")
            print("[hotkey] Make sure you are in the 'input' group: sudo usermod -aG input $USER")
            return False

        self._running = True
        for dev in keyboards:
            t = threading.Thread(target=self._watch_device, args=(dev,), daemon=True)
            t.start()
            self._threads.append(t)

        print(f"[hotkey] Listening on {len(keyboards)} keyboard device(s) via evdev")
        return True

    def _watch_device(self, dev):
        WINDOW  = 0.5   # max gap between first and second Ctrl-down
        TAP_MAX = 0.4   # max hold duration to count as a clean tap

        tap1_down  = 0.0
        tap1_up    = 0.0
        tap1_done  = False
        dirty      = False
        ptt_active = False

        try:
            for event in dev.read_loop():
                if not self._running:
                    break
                if event.type != ecodes.EV_KEY:
                    continue

                key   = event.code
                value = event.value   # 0=up 1=down 2=repeat
                if value == 2:
                    continue

                is_ctrl = key in _CTRL_KEYS
                now = time.monotonic()

                if not is_ctrl and value == 1:
                    dirty     = True
                    tap1_done = False

                elif is_ctrl and value == 1:   # Ctrl DOWN
                    if dirty:
                        tap1_down = now
                        tap1_done = False
                        dirty     = False
                    elif not tap1_done:
                        tap1_down = now
                    else:
                        gap = now - tap1_down
                        if gap < WINDOW:
                            if self._mode == "push_to_talk":
                                ptt_active = True
                            self._fire()
                            tap1_done = False
                            dirty     = True
                        else:
                            tap1_down = now
                            tap1_done = False

                elif is_ctrl and value == 0:   # Ctrl UP
                    hold_time = now - tap1_down
                    if not tap1_done and not dirty and hold_time < TAP_MAX:
                        tap1_done = True
                        tap1_up   = now

                    if ptt_active:
                        ptt_active = False
                        if self._on_stop:
                            self._on_stop()

                    if tap1_done and (now - tap1_up) > WINDOW:
                        tap1_done = False

                if key == ecodes.KEY_ENTER and value == 1 and self._on_enter:
                    self._on_enter()

        except OSError:
            pass  # Device disconnected

    def _fire(self):
        with self._lock:
            if self._active:
                return
            self._active = True
        try:
            self._on_trigger()
        finally:
            with self._lock:
                self._active = False

    def stop(self):
        self._running = False

    def join(self):
        for t in self._threads:
            t.join()


# ── pynput (macOS + Windows) ──────────────────────────────────────────────────

class _PynputHotkeyListener:
    """
    macOS / Windows global hotkey listener using pynput.

    Replicates the exact same double-tap Ctrl state machine as _EvdevHotkeyListener.
    All pynput callbacks run on the listener thread; _lock protects shared state.
    _fire() uses a separate lock to prevent re-entrant triggers.
    """

    WINDOW  = 0.5   # seconds — max gap between first and second Ctrl-down
    TAP_MAX = 0.4   # seconds — max hold duration to count as a clean tap

    def __init__(self, hotkey: str, on_trigger: Callable[[], None],
                 on_enter: Optional[Callable[[], None]] = None,
                 mode: str = "toggle",
                 on_stop: Optional[Callable[[], None]] = None):
        self._on_trigger = on_trigger
        self._on_enter   = on_enter
        self._mode       = mode
        self._on_stop    = on_stop
        self._listener   = None
        self._lock       = threading.Lock()   # protects state machine vars
        self._fire_lock  = threading.Lock()   # prevents re-entrant fire
        self._active     = False

        # State machine (all accesses under _lock)
        self._tap1_down  = 0.0
        self._tap1_up    = 0.0
        self._tap1_done  = False
        self._dirty      = False
        self._ptt_active = False

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_ctrl(key) -> bool:
        try:
            from pynput.keyboard import Key
            return key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r)
        except Exception:
            return False

    @staticmethod
    def _is_enter(key) -> bool:
        try:
            from pynput.keyboard import Key
            return key == Key.enter
        except Exception:
            return False

    # ── pynput callbacks ──────────────────────────────────────────────────────

    def _on_press(self, key):
        now     = time.monotonic()
        is_ctrl = self._is_ctrl(key)
        do_fire = False

        with self._lock:
            if not is_ctrl:
                # Any non-Ctrl key dirties the window
                self._dirty     = True
                self._tap1_done = False
                return

            # Ctrl DOWN
            if self._dirty:
                # Reset: begin a fresh first tap
                self._tap1_down = now
                self._tap1_done = False
                self._dirty     = False

            elif not self._tap1_done:
                # First tap is starting
                self._tap1_down = now

            else:
                # Possible second tap — check timing
                gap = now - self._tap1_down
                if gap < self.WINDOW:
                    do_fire = True
                    if self._mode == "push_to_talk":
                        self._ptt_active = True
                    self._tap1_done = False
                    self._dirty     = True   # block immediate triple-tap
                else:
                    # Too slow — restart as a new first tap
                    self._tap1_down = now
                    self._tap1_done = False

        if do_fire:
            threading.Thread(target=self._fire, daemon=True).start()

    def _on_release(self, key):
        now      = time.monotonic()
        is_ctrl  = self._is_ctrl(key)
        is_enter = self._is_enter(key)

        if is_enter and self._on_enter:
            self._on_enter()
            return

        if not is_ctrl:
            return

        call_stop = False
        with self._lock:
            hold_time = now - self._tap1_down
            if not self._tap1_done and not self._dirty and hold_time < self.TAP_MAX:
                self._tap1_done = True
                self._tap1_up   = now

            if self._ptt_active:
                self._ptt_active = False
                call_stop = True

            if self._tap1_done and (now - self._tap1_up) > self.WINDOW:
                self._tap1_done = False

        if call_stop and self._on_stop:
            self._on_stop()

    # ── fire / start / stop ───────────────────────────────────────────────────

    def _fire(self):
        with self._fire_lock:
            if self._active:
                return
            self._active = True
        try:
            self._on_trigger()
        finally:
            with self._fire_lock:
                self._active = False

    def start(self) -> bool:
        try:
            from pynput import keyboard as kb
        except ImportError:
            print("[hotkey] pynput not installed. Run: pip install pynput")
            return False

        try:
            self._listener = kb.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
            if sys.platform == "darwin":
                print("[hotkey] Listening via pynput (macOS)")
                print("[hotkey] No response? System Settings → Privacy & Security")
                print("[hotkey]   → Accessibility → add your terminal app")
            else:
                print("[hotkey] Listening via pynput (Windows)")
            return True
        except Exception as e:
            print(f"[hotkey] Failed to start listener: {e}")
            return False

    def stop(self):
        if self._listener:
            self._listener.stop()

    def join(self):
        if self._listener:
            self._listener.join()


# ── Public factory ────────────────────────────────────────────────────────────

def HotkeyListener(hotkey: str,
                   on_trigger: Callable[[], None],
                   on_enter: Optional[Callable[[], None]] = None,
                   mode: str = "toggle",
                   on_stop: Optional[Callable[[], None]] = None):
    """
    Return the appropriate HotkeyListener for the current platform.

    The returned object exposes start(), stop(), and join() — identical on all
    platforms so callers need no platform awareness.

    Linux   → _EvdevHotkeyListener  (direct /dev/input access)
    macOS   → _PynputHotkeyListener (requires Accessibility permission)
    Windows → _PynputHotkeyListener
    """
    if sys.platform == "linux":
        return _EvdevHotkeyListener(hotkey, on_trigger, on_enter, mode, on_stop)
    return _PynputHotkeyListener(hotkey, on_trigger, on_enter, mode, on_stop)
