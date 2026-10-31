"""Resolve explicit voice-command corrections before any action."""
import re

MARKERS = ("no i mean", "no i meant", "sorry i meant", "scratch that", "no actually", "actually i meant")

def final_request(text):
    normalized = re.sub(r"[,;.!?]+", " ", text.lower())
    found = [(normalized.rfind(marker), marker) for marker in MARKERS if marker in normalized]
    if not found:
        return text, False
    index, marker = max(found)
    if index and normalized[index - 1].isalnum():
        return text, False
    command = normalized[index + len(marker):].strip()
    if not command:
        raise ValueError("What should I do instead? Nothing was run.")
    return command, True
