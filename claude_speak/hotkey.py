"""
Global hotkey listener using evdev — reads raw keyboard input directly.

Why evdev:
  - Works on Wayland natively (no compositor support needed)
  - No X11 required
  - Reads /dev/input/event* directly (user must be in 'input' group)
  - Supports modifier-only combos like Ctrl+Shift

Trigger: fires when BOTH Ctrl and Shift are held and then released
together (without any other key pressed in between). This is a
"chord release" pattern — press both, let go, recording starts.

Requires: pip install evdev
          user in 'input' group (already set up)
"""
import threading
import time
from typing import Callable

try:
    import evdev
    from evdev import ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


# Key codes for modifiers
CTRL_KEYS  = {ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL}  if EVDEV_AVAILABLE else set()
SHIFT_KEYS = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT} if EVDEV_AVAILABLE else set()


def _find_keyboards():
    """Return all evdev devices that look like keyboards."""
    if not EVDEV_AVAILABLE:
        return []
    keyboards = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            # Must have key events and at least one letter key
            if ecodes.EV_KEY in caps and ecodes.KEY_A in caps.get(ecodes.EV_KEY, []):
                keyboards.append(dev)
        except Exception:
            pass
    return keyboards


class HotkeyListener:
    def __init__(self, hotkey: str, on_trigger: Callable[[], None],
                 on_enter: Callable[[], None] | None = None,
                 mode: str = "toggle",
                 on_stop: Callable[[], None] | None = None):
        """
        hotkey:     ignored — always uses Ctrl+Shift chord via evdev
        on_trigger: called to start recording
        on_enter:   called when Enter is pressed (used to stop recording early)
        mode:       "toggle" — fire on chord release (existing behaviour)
                    "push_to_talk" — fire on chord press, call on_stop on release
        on_stop:    called when keys are released in push_to_talk mode
        """
        self._hotkey = hotkey
        self._on_trigger = on_trigger
        self._on_enter = on_enter
        self._mode = mode
        self._on_stop = on_stop
        self._threads: list[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        self._active = False

    def start(self) -> bool:
        if not EVDEV_AVAILABLE:
            print("[hotkey] evdev not installed. Run: pip install evdev")
            return False

        keyboards = _find_keyboards()
        if not keyboards:
            print("[hotkey] No keyboard devices found in /dev/input")
            print("[hotkey] Make sure you are in the 'input' group")
            return False

        self._running = True
        for dev in keyboards:
            t = threading.Thread(
                target=self._watch_device,
                args=(dev,),
                daemon=True,
            )
            t.start()
            self._threads.append(t)

        print(f"[hotkey] Listening on {len(keyboards)} keyboard device(s) via evdev")
        return True

    def _watch_device(self, dev):
        """
        Double-tap Ctrl to trigger.
        State machine: track Ctrl press/release pairs. If two complete
        tap cycles (down+up) happen within 500ms with no other key between,
        fire the trigger.
        """
        import time as _time

        WINDOW = 0.5        # 500ms between first Ctrl-down and second Ctrl-down
        TAP_MAX = 0.4       # single tap must be shorter than this (not a hold)

        # State
        tap1_down  = 0.0    # time of first Ctrl key-down
        tap1_up    = 0.0    # time of first Ctrl key-up
        tap1_done  = False  # first tap (down+up) completed cleanly
        dirty      = False  # a non-Ctrl key was pressed, invalidate window
        ptt_active = False

        try:
            for event in dev.read_loop():
                if not self._running:
                    break
                if event.type != ecodes.EV_KEY:
                    continue

                key   = event.code
                value = event.value  # 0=up 1=down 2=repeat
                if value == 2:       # ignore repeats
                    continue

                is_ctrl = key in CTRL_KEYS
                now = _time.monotonic()

                if not is_ctrl and value == 1:
                    # Non-Ctrl key pressed — dirty the window
                    dirty     = True
                    tap1_done = False

                elif is_ctrl and value == 1:  # Ctrl DOWN
                    if dirty:
                        # Reset — start a fresh first tap
                        tap1_down  = now
                        tap1_done  = False
                        dirty      = False

                    elif not tap1_done:
                        # First tap down
                        tap1_down = now

                    else:
                        # Second tap down — check timing
                        gap = now - tap1_down
                        if gap < WINDOW:
                            # ✓ Double-tap confirmed
                            if self._mode == "push_to_talk":
                                ptt_active = True
                                self._fire()
                            else:
                                self._fire()
                            # Reset state
                            tap1_done = False
                            dirty     = True   # prevent immediate triple-tap
                        else:
                            # Too slow — this becomes a new first tap
                            tap1_down = now
                            tap1_done = False

                elif is_ctrl and value == 0:  # Ctrl UP
                    hold_time = now - tap1_down
                    if not tap1_done and not dirty and hold_time < TAP_MAX:
                        tap1_done = True
                        tap1_up   = now

                    # Push-to-talk: releasing Ctrl stops recording
                    if ptt_active:
                        ptt_active = False
                        if self._on_stop:
                            self._on_stop()

                    # Reset if window expired
                    if tap1_done and (now - tap1_up) > WINDOW:
                        tap1_done = False

                # Enter key stops recording
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
