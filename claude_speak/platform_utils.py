"""
Platform detection and OS-appropriate directory helpers for claude_speak.
"""
import os
import sys


def get_platform() -> str:
    """Return 'linux', 'macos', or 'windows'."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return "linux"


def get_config_dir() -> str:
    """
    Return the OS-appropriate config directory for claude_speak.

    Linux:   ~/.config/claude_speak/
    macOS:   ~/Library/Application Support/claude_speak/
    Windows: %APPDATA%\\claude_speak\\
    """
    p = get_platform()
    if p == "macos":
        return os.path.expanduser("~/Library/Application Support/claude_speak")
    if p == "windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "claude_speak")
    return os.path.expanduser("~/.config/claude_speak")


def get_data_dir() -> str:
    """
    Return the OS-appropriate data directory for claude_speak.

    Linux:   ~/.local/share/claude_speak/
    macOS:   ~/Library/Application Support/claude_speak/
    Windows: %APPDATA%\\claude_speak\\
    """
    p = get_platform()
    if p == "macos":
        return os.path.expanduser("~/Library/Application Support/claude_speak")
    if p == "windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "claude_speak")
    return os.path.expanduser("~/.local/share/claude_speak")
