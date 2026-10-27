"""Conservative recovery of a leading lights-off sentence in voice transcripts."""
import re
from .discovery import lighting, norm

# Never discard these terms as background chatter.
VETO = re.compile(r"\b(?:no|not|don't|dont|do not|never|wait|stop|cancel|actually|instead|except|but|on|off|turn|switch|dim|brighten|set|start|end|open|close|lock|unlock|play|pause|resume|goodnight|bedtime|morning|night|and|then)\b")

def recover_off(hass, text):
    """Return only a fully resolved leading OFF sentence, or None.

    This is text-based recovery, not audio denoising or speaker recognition.
    """
    parts = re.split(r'[.!?]\s+', text.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    first, tail = parts
    try:
        step = lighting(hass, first)
    except ValueError:
        return None
    if not step or step['kind'] != 'light' or step['name'] != 'turn_off':
        return None
    # An exact repetition of the same command adds no new target/action.
    tail = re.sub(r'(?<!\w)' + re.escape(norm(first)) + r'(?!\w)', '', norm(tail))
    # "But" alone often introduces unrelated TV chatter; all real negations
    # and corrections below still veto recovery.
    tail = re.sub(r'^but\s+', '', tail)
    if VETO.search(tail):
        return None
    return first
