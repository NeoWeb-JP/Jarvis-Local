"""Resolve explicit voice-command corrections before device actions."""
import re

_MARKERS = re.compile(
    r"\b(?:no\s+i\s+mean|no\s+i\s+meant|sorry\s+i\s+meant|"
    r"scratch\s+that|no\s+actually|actually\s+i\s+meant)\b",
    re.IGNORECASE,
)


def final_request(text):
    # Incidental punctuation has no command significance.
    normalized = re.sub(r"[,;.!?]+", " ", text)
    matches = list(_MARKERS.finditer(normalized))
    if not matches:
        return text, False
    command = normalized[matches[-1].end():].strip()
    if not command:
        raise ValueError("What should I do instead? Nothing was run.")
    return command, True
