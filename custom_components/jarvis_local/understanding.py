"""Deterministic conversational grammar; never guess a device or action."""
import re


def normalize_request(text):
    original = text
    text = re.sub(r"\s+", " ", text.replace("’", "'")).strip()
    # Assistant names and leading hesitation words are not target names.
    text = re.sub(r"^(?:(?:um|uh|erm)[, ]+)+", "", text, flags=re.I)
    text = re.sub(r"^(?:hey[ ,]+)?(?:declan|jarvis)[ ,:.!?]+", "", text, flags=re.I)
    prefix = ""
    for option in ("preview ", "dry run ", "what would you do if i said "):
        if text.lower().startswith(option):
            prefix, text = option, text[len(option):]
            break
    polite = r"^(?:please\s+)?(?:would you mind|(?:can|could|would|will) you(?: please)?)\s+"
    wrapped = bool(re.match(polite, text, re.I))
    text = re.sub(polite, "", text, flags=re.I)
    text = re.sub(r"^please\s+", "", text, flags=re.I)
    # Bounded verb forms only; negatives and trailing clauses remain intact.
    if wrapped:
        text = re.sub(r"^turning\b", "turn", text, flags=re.I)
        text = re.sub(r"^switching\b", "switch", text, flags=re.I)
        text = re.sub(r"^starting\b", "start", text, flags=re.I)
        text = re.sub(r"^finding\b", "find", text, flags=re.I)
    text = re.sub(r"^put (.+?) (on|off)([.!?]*)$", r"turn \1 \2\3", text, flags=re.I)
    match = re.fullmatch(r"make (.+?(?:lights?|lamps?|spotlights?)) (brighter|dimmer)([.!?]*)", text, re.I)
    if match:
        text = ("brighten " if match[2].lower() == "brighter" else "dim ") + match[1] + match[3]
    if re.match(r"^(?:turn|switch|set|dim|brighten|start|stop|be quiet|shut up)\b", text, re.I):
        text = re.sub(r"\s+(?:for me(?: please)?|please)[.!?]*$", "", text, flags=re.I)
    text = prefix + text
    return text, (["normalized conversational wording"] if text != original else [])
