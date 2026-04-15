"""
Install claude_speak as a CLI command:

    pip install -e .

After install, run with:

    claude_speak

Platform-specific dependencies are resolved automatically via PEP 508 markers:
  Linux   — evdev (keyboard input via /dev/input)
  macOS   — pynput + pyperclip
  Windows — pynput + pyperclip (plyer is optional for richer notifications)
"""
from setuptools import setup, find_packages

setup(
    name="claude_speak",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        # Core — all platforms
        "faster-whisper>=0.9.0",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "scipy>=1.11.0",

        # Linux: raw keyboard input via evdev
        "evdev>=1.6.0; sys_platform == 'linux'",

        # macOS / Windows: global hotkey + clipboard injection
        "pynput>=1.7.6; sys_platform != 'linux'",
        "pyperclip>=1.8.2; sys_platform != 'linux'",
    ],
    extras_require={
        # Optional richer Windows notifications
        "windows-notify": ["plyer>=2.1.0"],
    },
    entry_points={
        "console_scripts": [
            "claude_speak=claude_speak.main:main",
            "claude_speak_gui=claude_speak.gui:main",
        ],
    },
)
