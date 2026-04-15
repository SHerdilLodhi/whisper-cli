"""
Shortcut phrase→command mapping for claude_speak.

check_shortcut() — checks if spoken text matches a configured shortcut phrase.
run_shortcut()   — executes the matched command.

Supports template variables like {query} in phrases:
  config shortcuts: {"search {query}": "xdg-open 'https://google.com/search?q={query}'"}
  spoken text:      "search python tutorials"
  → command:        "xdg-open 'https://google.com/search?q=python tutorials'"
"""
import re
import subprocess
from typing import Optional


def check_shortcut(text: str, shortcuts: dict) -> Optional[str]:
    """
    Check whether the given text matches any shortcut phrase.

    Matching is case-insensitive. Template variables ({name}) in the phrase
    capture the corresponding portion of the spoken text and are substituted
    into the command string.

    Returns the resolved command string on a match, or None if no match.
    """
    if not shortcuts or not text:
        return None

    normalized = text.strip().lower()

    for phrase, command in shortcuts.items():
        phrase_lower = phrase.strip().lower()

        # Find all template variable names in the phrase, e.g. {query}
        var_names = re.findall(r"\{(\w+)\}", phrase_lower)

        if var_names:
            # Build a regex pattern that captures each variable
            pattern = re.escape(phrase_lower)
            for var in var_names:
                # Replace the escaped placeholder with a named capture group
                pattern = pattern.replace(
                    re.escape("{" + var + "}"),
                    r"(?P<" + var + r">.+?)",
                )
            pattern = "^" + pattern + "$"

            m = re.match(pattern, normalized)
            if m:
                resolved = command
                for var in var_names:
                    resolved = resolved.replace("{" + var + "}", m.group(var))
                return resolved
        else:
            # Plain phrase — exact case-insensitive match
            if normalized == phrase_lower:
                return command

    return None


def run_shortcut(command: str) -> None:
    """
    Execute the command in a subprocess shell (non-blocking).
    """
    try:
        subprocess.Popen(command, shell=True)
    except Exception as e:
        print(f"[shortcuts] Failed to run command: {e}")
