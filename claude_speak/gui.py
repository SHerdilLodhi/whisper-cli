"""
claude_speak GUI — professional floating voice panel.
Animated waveform, dark theme, minimal controls.
"""
import sys, os, threading, contextlib, warnings, math, random, time

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

for _p in ["/usr/lib/python3/dist-packages", "/usr/lib/python3.12/dist-packages"]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if sys.platform != "linux":
    print("[gui] The GUI requires GTK4 + Adwaita, which are only available on Linux.")
    print("[gui] Use the CLI instead:  claude_speak")
    sys.exit(1)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk

from .config import Config
from .audio import AudioCapture
from .transcribe import load_model, transcribe, strip_punctuation as _strip_punct
from .inject import get_active_window, inject_text
from .notify import beep, notify
from .shortcuts import check_shortcut, run_shortcut
from .hotkey import HotkeyListener

# ── Palette (Catppuccin Mocha) ────────────────────────────────────────────────
_BASE      = "#1e1e2e"
_SURFACE0  = "#313244"
_SURFACE1  = "#45475a"
_OVERLAY   = "#6c7086"
_TEXT      = "#cdd6f4"
_SUBTEXT   = "#a6adc8"
_BLUE      = "#89b4fa"
_RED       = "#f38ba8"
_PEACH     = "#fab387"
_GREEN     = "#a6e3a1"
_LAVENDER  = "#b4befe"

CSS = f"""
window, .cs-bg {{
    background-color: {_BASE};
}}
headerbar {{
    background-color: {_BASE};
    border-bottom: 1px solid {_SURFACE0};
    box-shadow: none;
    min-height: 36px;
}}
headerbar .title {{
    color: {_SUBTEXT};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
.state-idle        {{ color: {_TEXT};    font-size: 16px; font-weight: 700; }}
.state-recording   {{ color: {_RED};     font-size: 16px; font-weight: 700; }}
.state-transcribing{{ color: {_PEACH};   font-size: 16px; font-weight: 700; }}
.state-loading     {{ color: {_GREEN};   font-size: 16px; font-weight: 700; }}
.hint {{
    color: {_OVERLAY};
    font-size: 11px;
    font-weight: 400;
}}
.sep {{ background-color: {_SURFACE0}; margin-top: 6px; margin-bottom: 6px; }}
.wbar {{
    border-radius: 3px;
    background-color: {_SURFACE1};
    min-width: 4px;
}}
.wbar-recording     {{ background-color: {_RED};   }}
.wbar-transcribing  {{ background-color: {_PEACH}; }}
.chip {{
    border-radius: 20px;
    background-color: {_SURFACE0};
    color: {_SUBTEXT};
    border: 1px solid {_SURFACE1};
    font-size: 11px;
    font-weight: 500;
    padding: 4px 12px;
    min-height: 0;
    min-width: 0;
}}
.chip:hover {{ background-color: {_SURFACE1}; color: {_TEXT}; }}
.chip.on  {{
    background-color: {_BLUE};
    color: {_BASE};
    border-color: {_BLUE};
    font-weight: 700;
}}
""".encode()

# ── Waveform DrawingArea ──────────────────────────────────────────────────────

class Waveform(Gtk.Box):
    """Animated bar waveform using GTK widgets — no Cairo required."""

    N   = 24
    MAX = 52
    MIN = 3

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        self.set_size_request(-1, 56)
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        self._state   = "idle"
        self._heights = [float(self.MIN)] * self.N
        self._targets = [float(self.MIN)] * self.N
        self._phase   = 0.0
        self._widgets = []

        for _ in range(self.N):
            bar = Gtk.Box()
            bar.set_size_request(4, self.MIN)
            bar.set_valign(Gtk.Align.CENTER)
            bar.add_css_class("wbar")
            self.append(bar)
            self._widgets.append(bar)

        GLib.timeout_add(40, self._tick)   # ~25 fps

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        css_map = {"recording": "wbar-recording", "transcribing": "wbar-transcribing"}
        for bar in self._widgets:
            bar.remove_css_class("wbar-recording")
            bar.remove_css_class("wbar-transcribing")
            if state in css_map:
                bar.add_css_class(css_map[state])

    def _tick(self):
        self._phase += 0.18

        if self._state == "recording":
            for i in range(self.N):
                self._targets[i] = random.randint(10, self.MAX)
        elif self._state == "transcribing":
            for i in range(self.N):
                self._targets[i] = self.MIN + (self.MAX - self.MIN) * abs(
                    math.sin(self._phase + i * 0.45))
        else:
            for i in range(self.N):
                self._targets[i] = self.MIN + 6 * abs(
                    math.sin(self._phase * 0.35 + i * 0.5))

        speed = 0.45 if self._state == "recording" else 0.2
        for i, bar in enumerate(self._widgets):
            self._heights[i] += (self._targets[i] - self._heights[i]) * speed
            bar.set_size_request(4, max(self.MIN, int(self._heights[i])))

        return True


# ── Main window ───────────────────────────────────────────────────────────────

def _hint(mode: str) -> str:
    return ("Double-tap Ctrl · hold to record · release to stop"
            if mode == "push_to_talk"
            else "Double-tap Ctrl to start  ·  Double-tap Ctrl to stop")


class ClaudeSpeakWindow(Adw.ApplicationWindow):

    def __init__(self, app, cfg: Config):
        super().__init__(application=app)
        self.cfg         = cfg
        self._audio      = AudioCapture(cfg)
        self._early_stop = threading.Event()
        self._is_recording = False
        self._timer_id   = None
        self._timer_val  = 0
        self._hotkey     = None

        self._apply_css()
        self._build_ui()
        self._start_hotkey()
        self._setup_tray()

        self.set_title("claude speak")
        self.set_default_size(320, 0)
        self.set_resizable(False)
        self.connect("close-request", lambda *_: self.set_visible(False) or True)

        # Load model
        self.mic_btn.set_sensitive(False)
        threading.Thread(target=self._load_model_bg, daemon=True).start()

    # ── CSS ───────────────────────────────────────────────────────────────────

    def _apply_css(self):
        p = Gtk.CssProvider()
        p.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), p,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Root toolbar view (Adw-native)
        tv = Adw.ToolbarView()

        # Header bar
        hb = Adw.HeaderBar()
        hb.set_show_end_title_buttons(True)
        tv.add_top_bar(hb)

        # Content
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_top(12)
        content.set_margin_bottom(14)
        content.set_margin_start(18)
        content.set_margin_end(18)

        # Waveform
        self.waveform = Waveform()
        self.waveform.set_margin_bottom(10)
        content.append(self.waveform)

        # State label
        self.state_lbl = Gtk.Label(label="Loading model...")
        self.state_lbl.add_css_class("state-loading")
        self.state_lbl.set_halign(Gtk.Align.START)
        content.append(self.state_lbl)

        # Hint label
        self.hint_lbl = Gtk.Label(label=_hint(self.cfg.trigger_mode))
        self.hint_lbl.add_css_class("hint")
        self.hint_lbl.set_halign(Gtk.Align.START)
        self.hint_lbl.set_margin_top(3)
        self.hint_lbl.set_margin_bottom(10)
        content.append(self.hint_lbl)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.add_css_class("sep")
        content.append(sep)

        # Controls row
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_halign(Gtk.Align.CENTER)
        row.set_margin_top(4)

        # Mode
        mode_list = Gtk.StringList.new(["Toggle", "Push to Talk"])
        self.mode_drop = Gtk.DropDown(model=mode_list)
        self.mode_drop.set_selected(0 if self.cfg.trigger_mode == "toggle" else 1)
        self.mode_drop.connect("notify::selected", self._on_mode)
        self.mode_drop.add_css_class("chip")
        row.append(self.mode_drop)

        # Model
        model_list = Gtk.StringList.new(["tiny", "base", "small"])
        _m = ["tiny", "base", "small"]
        self.model_drop = Gtk.DropDown(model=model_list)
        self.model_drop.set_selected(_m.index(self.cfg.model) if self.cfg.model in _m else 1)
        self.model_drop.connect("notify::selected", self._on_model)
        self.model_drop.add_css_class("chip")
        row.append(self.model_drop)

        # Sound toggle
        self.sound_btn = Gtk.ToggleButton(label="Sound  On" if self.cfg.sound_feedback else "Sound  Off")
        self.sound_btn.set_active(self.cfg.sound_feedback)
        self.sound_btn.add_css_class("chip")
        if self.cfg.sound_feedback:
            self.sound_btn.add_css_class("on")
        self.sound_btn.connect("toggled", self._on_sound)
        row.append(self.sound_btn)

        # Hidden mic button (needed for push-to-talk gesture only, not shown)
        self.mic_btn = Gtk.Button()
        self.mic_btn.set_visible(False)

        content.append(row)
        tv.set_content(content)
        self.set_content(tv)

    # ── Hotkey ────────────────────────────────────────────────────────────────

    def _start_hotkey(self):
        def on_trigger():
            GLib.idle_add(self._hotkey_fire)

        self._hotkey = HotkeyListener(
            hotkey="<ctrl>+<shift>",
            on_trigger=on_trigger,
            on_enter=None,
            mode=self.cfg.trigger_mode,
            on_stop=lambda: self._early_stop.set(),
        )
        self._hotkey.start()

    def _hotkey_fire(self):
        if not self._is_recording:
            self._start_pipeline()
        elif self.cfg.trigger_mode == "toggle":
            self._early_stop.set()
        return False

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _start_pipeline(self):
        if self._is_recording:
            return
        self._early_stop.clear()
        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self):
        self._is_recording = True
        GLib.idle_add(self._ui_start)

        if self.cfg.sound_feedback:
            beep(880, 0.08, 0.3)

        window_id = get_active_window()
        audio = self._audio.record(early_stop_event=self._early_stop)
        self._is_recording = False

        if self.cfg.sound_feedback:
            beep(660, 0.08, 0.3)

        GLib.idle_add(self._ui_stop)

        if audio is None:
            GLib.idle_add(self._set_state, "idle", "● Ready")
            return

        GLib.idle_add(self._set_state, "transcribing", "Transcribing...")

        text = transcribe(audio, self.cfg.sample_rate, self.cfg.language)
        if not text:
            GLib.idle_add(self._set_state, "idle", "● Ready")
            return

        if self.cfg.strip_punctuation:
            text = _strip_punct(text)

        if self.cfg.shortcuts:
            cmd = check_shortcut(text, self.cfg.shortcuts)
            if cmd:
                run_shortcut(cmd)
                GLib.idle_add(self._set_state, "idle", "● Ready")
                return

        if self.cfg.notifications:
            notify("claude_speak", text)

        inject_text(text, window_id, delay_before=self.cfg.inject_delay)
        GLib.idle_add(self._set_state, "idle", "● Ready")

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _ui_start(self):
        self._timer_val = 0
        self.waveform.set_state("recording")
        self._set_state("recording", "● Recording  0s")
        self._timer_id = GLib.timeout_add(1000, self._tick)
        return False

    def _ui_stop(self):
        self.waveform.set_state("idle")
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        return False

    def _tick(self):
        self._timer_val += 1
        self._set_state("recording", f"● Recording  {self._timer_val}s")
        return True

    def _set_state(self, kind: str, text: str):
        self.state_lbl.set_text(text)
        for c in ("state-idle", "state-recording", "state-transcribing", "state-loading"):
            self.state_lbl.remove_css_class(c)
        self.state_lbl.add_css_class(f"state-{kind}")
        if kind in ("recording", "transcribing"):
            self.waveform.set_state(kind)
        elif kind == "idle":
            self.waveform.set_state("idle")
        return False

    # ── Controls ──────────────────────────────────────────────────────────────

    def _on_mode(self, drop, _):
        mode = "toggle" if drop.get_selected() == 0 else "push_to_talk"
        self.cfg.trigger_mode = mode
        self.cfg.save()
        self.hint_lbl.set_text(_hint(mode))
        if self._hotkey:
            self._hotkey.stop()
        self._start_hotkey()

    def _on_model(self, drop, _):
        new = ["tiny", "base", "small"][drop.get_selected()]
        if new == self.cfg.model:
            return
        self.cfg.model = new
        self.cfg.save()
        self.mic_btn.set_sensitive(False)
        GLib.idle_add(self._set_state, "loading", "Loading model...")
        threading.Thread(target=self._load_model_bg, daemon=True).start()

    def _on_sound(self, btn):
        on = btn.get_active()
        self.cfg.sound_feedback = on
        self.cfg.save()
        btn.set_label("Sound  On" if on else "Sound  Off")
        btn.add_css_class("on") if on else btn.remove_css_class("on")

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model_bg(self):
        with open(os.devnull, "w") as dn, contextlib.redirect_stderr(dn):
            load_model(self.cfg.model)
        GLib.idle_add(self._set_state, "idle", "● Ready")
        GLib.idle_add(self.mic_btn.set_sensitive, True)

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = None
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse([4, 4, 60, 60], fill=(137, 180, 250, 255))
            d.ellipse([22, 12, 42, 40], fill=(30, 30, 46, 255))
            d.rectangle([29, 40, 35, 52], fill=(30, 30, 46, 255))
            menu = pystray.Menu(
                pystray.MenuItem("Show / Hide", lambda *_: GLib.idle_add(
                    lambda: self.set_visible(not self.get_visible()) or False)),
                pystray.MenuItem("Quit", lambda *_: GLib.idle_add(
                    self.get_application().quit)),
            )
            self._tray = pystray.Icon("claude_speak", img, "claude_speak", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            pass


# ── App ───────────────────────────────────────────────────────────────────────

class _App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.claudespeak.gui")
        self._win = None

    def do_activate(self):
        if self._win is None:
            self._win = ClaudeSpeakWindow(self, Config.load())
        self._win.present()


def main():
    app = _App()
    sys.exit(app.run(sys.argv))
