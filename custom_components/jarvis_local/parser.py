"""Strict, bounded command recognition. No fuzzy device execution."""
import re

def parse(text):
    text = text.lower().replace("’", "'").strip()
    text = re.sub(r"[.!?,]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:hey )?jarvis\s+", "", text)
    text = re.sub(r"\s+jarvis$", "", text)
    text = re.sub(r"^please\s+|\s+please$", "", text).strip()
    if text in {"good morning", "morning", "start the morning routine"}:
        return "jarvis_local_good_morning", {}
    if text in {"good night", "goodnight", "it's bedtime", "time for bed", "shut the house down", "start the bedtime routine"}:
        return "jarvis_local_good_night", {}
    match = re.fullmatch(r"(?:(start|end|stop|turn on|turn off|toggle) )?(movie time|cinema time|cinema mode)", text)
    if match:
        action = {"start":"start", "turn on":"start", "end":"end", "stop":"end", "turn off":"end"}.get(match[1], "toggle")
        return "jarvis_local_movie", {"requested_action":action}
    return None
