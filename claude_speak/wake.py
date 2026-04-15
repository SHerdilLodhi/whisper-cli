"""
Voice wake word detection — "Hey Claude"

STATUS: Stub / documented path for v2.

RECOMMENDED APPROACH (not yet implemented):
  Use `openwakeword` — open source, offline, runs on CPU:
    pip install openwakeword

  openwakeword ships pre-trained models. "Hey Claude" is not in the default
  model set, but you can:
    1. Use the closest available model ("hey_jarvis", "alexa") as a proxy
       — expect false positive/negative rates
    2. Train a custom model using openwakeword's training pipeline:
       https://github.com/dscripka/openWakeWord#training-new-models
       You need ~20 positive audio samples of "Hey Claude" + noise augmentation

  Integration pattern:
    - Run a continuous low-sample-rate (16kHz) stream in a background thread
    - Feed chunks to openwakeword's model every 80ms
    - When confidence > threshold (~0.7), trigger the same callback as Ctrl+Space

TRADEOFF vs keyboard hotkey:
  Pros: hands-free, natural activation
  Cons: 2-5% false positive rate, uses ~10-15% CPU continuously on low-end hardware,
        model download ~50MB, training effort for custom wake word

SIMPLIFIED FALLBACK (working but inefficient):
  Record 2-second chunks continuously, run tiny Whisper on each chunk,
  check if text contains "hey claude". This works but burns CPU.
  Not recommended for production.

For now, wake word is disabled. The keyboard hotkey (Ctrl+Space) is the
primary and only trigger in v1.
"""


class WakeWordListener:
    """Placeholder. Implement with openwakeword for v2."""

    def __init__(self, phrase: str, on_trigger):
        self.phrase = phrase
        self.on_trigger = on_trigger

    def start(self):
        # Not implemented — see module docstring
        pass

    def stop(self):
        pass
