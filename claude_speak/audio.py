"""
Audio capture with RMS-based silence detection.

Records from the default system microphone until:
  - silence is detected for `config.silence_duration` seconds, OR
  - `config.max_duration` seconds have elapsed

Returns raw float32 numpy array at 16kHz (Whisper's expected format).
"""
import time
import threading
import numpy as np
import sounddevice as sd
from typing import Optional
from .config import Config


class AudioCapture:
    def __init__(self, config: Config):
        self.cfg = config
        self._chunks: list[np.ndarray] = []
        self._stop_event = threading.Event()
        self._has_speech = False

    def stop_early(self):
        """Call this to stop recording immediately (e.g. user pressed Enter)."""
        self._stop_event.set()

    def _measure_noise_floor(self) -> float:
        """
        Record 0.5s of ambient audio and return the peak RMS.
        Used to set a dynamic silence threshold that adapts to the environment.
        """
        chunks = []
        def cb(indata, frames, t, status):
            chunks.append(np.sqrt(np.mean(indata[:, 0] ** 2)))
        with sd.InputStream(samplerate=self.cfg.sample_rate, channels=1,
                            blocksize=self.cfg.blocksize, dtype="float32", callback=cb):
            time.sleep(0.5)
        if not chunks:
            return self.cfg.silence_threshold
        # Use peak * 3 as threshold — well above background, below speech
        return float(np.max(chunks)) * 3.0

    def record(self, early_stop_event: Optional[threading.Event] = None) -> Optional[np.ndarray]:
        """
        Blocks until recording is complete.
        Returns float32 audio array, or None if nothing was captured.

        early_stop_event: optional external event — set it to stop recording immediately.
        """
        self._chunks = []
        self._stop_event.clear()
        self._has_speech = False

        # Measure ambient noise and set threshold dynamically.
        # threshold = noise_floor * 4 so speech (much louder) registers clearly.
        # Minimum of 0.01 to avoid hair-trigger on near-silent environments.
        noise_floor = self._measure_noise_floor()
        threshold = max(noise_floor * 4, 0.01)

        # Frames of silence needed before we stop
        silence_frame_count = int(
            self.cfg.silence_duration * self.cfg.sample_rate / self.cfg.blocksize
        )
        silent_frames = 0
        start_time = time.monotonic()
        self._start_time = start_time
        self._threshold = threshold

        def callback(indata: np.ndarray, frames: int, time_info, status):
            nonlocal silent_frames

            if status:
                # Non-fatal: just log audio device warnings
                print(f"[audio] status: {status}")

            chunk = indata[:, 0].copy()  # Mono: take first channel
            self._chunks.append(chunk)

            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if rms < threshold:
                silent_frames += 1
            else:
                silent_frames = 0
                self._has_speech = True

            elapsed = time.monotonic() - start_time

            # Stop conditions
            if elapsed > self.cfg.max_duration:
                self._stop_event.set()
                raise sd.CallbackStop()

            # Stop if external early_stop_event was set (e.g. user pressed Enter)
            if early_stop_event and early_stop_event.is_set():
                self._stop_event.set()
                raise sd.CallbackStop()

            # Only stop on silence AFTER speech has been detected
            if (
                self._has_speech
                and elapsed > self.cfg.min_speech_duration
                and silent_frames >= silence_frame_count
            ):
                self._stop_event.set()
                raise sd.CallbackStop()

        try:
            with sd.InputStream(
                samplerate=self.cfg.sample_rate,
                channels=self.cfg.channels,
                blocksize=self.cfg.blocksize,
                dtype="float32",
                callback=callback,
            ):
                self._stop_event.wait(timeout=self.cfg.max_duration + 2)
        except sd.CallbackStop:
            pass
        except sd.PortAudioError as e:
            print(f"[audio] Microphone disconnected or unavailable: {e}")
            print("[audio] Please reconnect your microphone and try again.")
            return None
        except Exception as e:
            print(f"[audio] Recording error: {e}")
            return None

        if not self._chunks:
            return None

        audio = np.concatenate(self._chunks)

        # Drop if too short to transcribe meaningfully
        duration = len(audio) / self.cfg.sample_rate
        if duration < self.cfg.min_speech_duration:
            return None

        return audio


def check_microphone() -> tuple[bool, str]:
    """
    Verify a default input device exists. Called at startup.
    Returns (ok: bool, device_name: str).
    """
    try:
        device = sd.query_devices(kind="input")
        name = device["name"]
        print(f"[audio] Microphone: {name}")
        return True, name
    except Exception as e:
        print(f"[audio] No microphone found: {e}")
        return False, "unknown"
