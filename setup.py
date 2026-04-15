"""
Install claude_speak as a CLI command:

    pip install -e .

After install, run with:

    claude_speak
"""
from setuptools import setup, find_packages

setup(
    name="claude_speak",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "openai-whisper>=20231117",
        "sounddevice>=0.4.6",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
        "pynput>=1.7.6",
    ],
    entry_points={
        "console_scripts": [
            "claude_speak=claude_speak.main:main",
            "claude_speak_gui=claude_speak.gui:main",
        ],
    },
    python_requires=">=3.9",
)
