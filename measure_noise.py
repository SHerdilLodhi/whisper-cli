"""Run this to measure your mic's background noise level."""
import sounddevice as sd
import numpy as np
import time

print("Measuring background noise for 3 seconds... stay quiet.")
time.sleep(1)

chunks = []
def callback(indata, frames, t, status):
    chunks.append(np.sqrt(np.mean(indata[:, 0] ** 2)))

with sd.InputStream(samplerate=16000, channels=1, blocksize=1024,
                    dtype='float32', callback=callback):
    time.sleep(3)

avg = float(np.mean(chunks))
peak = float(np.max(chunks))
recommended = round(peak * 2.5, 3)

print(f"Average noise RMS : {avg:.4f}")
print(f"Peak noise RMS    : {peak:.4f}")
print(f"Recommended threshold: {recommended}")
print()
print(f"Run this to apply:")
print(f'  echo \'{{"hotkey": "<ctrl>+<shift>+<space>", "silence_threshold": {recommended}, "silence_duration": 0.6}}\' > ~/.config/claude_speak/config.json')
