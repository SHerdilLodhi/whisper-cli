"""
Speech-to-text using faster-whisper (CTranslate2 backend).

faster-whisper is 4x faster than openai-whisper on CPU with identical accuracy.
7s audio → ~2s transcription instead of ~10s.

Install: pip install faster-whisper
"""
import os
import tempfile
import numpy as np
import scipy.io.wavfile as wav
from typing import Optional

_model = None
_model_name: Optional[str] = None


def load_model(model_name: str) -> None:
    global _model, _model_name
    from faster_whisper import WhisperModel
    _model_name = model_name
    # cpu with int8 quantization — fastest on CPU, no accuracy loss
    _model = WhisperModel(model_name, device="cpu", compute_type="int8")

    # Pre-warm: transcribe 0.5s of silence to eliminate first-use latency.
    # The model JIT-compiles kernels on the first inference call; doing it
    # here means the user's first real transcription feels instant.
    try:
        silence = np.zeros(int(16000 * 0.5), dtype=np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            warmup_path = f.name
        import scipy.io.wavfile as _wav
        _pcm = (silence * 32767).astype(np.int16)
        _wav.write(warmup_path, 16000, _pcm)
        list(_model.transcribe(warmup_path, language="en", beam_size=1)[0])
        try:
            os.unlink(warmup_path)
        except OSError:
            pass
    except Exception:
        pass  # Pre-warm failure is non-fatal


def strip_punctuation(text: str) -> str:
    """
    Strip trailing punctuation characters (. , ; ! ?) and whitespace from text.
    Only removes from the right end so mid-sentence punctuation is preserved.
    """
    return text.rstrip(" \t.,;!?")


def transcribe(audio: np.ndarray, sample_rate: int, language: Optional[str] = None) -> Optional[str]:
    if _model is None:
        raise RuntimeError("Model not loaded. Call load_model() first.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        wav.write(tmp_path, sample_rate, pcm)

        segments, _ = _model.transcribe(
            tmp_path,
            language=language,
            beam_size=1,          # Fastest decoding
            vad_filter=True,      # Skip silent parts
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return text if text else None

    except Exception as e:
        print(f"[transcribe] Error: {e}")
        return None

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
