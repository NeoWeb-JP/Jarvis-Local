"""Speaker-aware morning replies, without guessing who is speaking."""
import random

NEUTRAL = (
    'Good morning. The house is waking up, and the morning routine is underway.',
    'Good morning. The morning routine is underway. I hope the coffee is ready.',
    'Morning. I have started the routine. The pets are probably already supervising.',
)
NAMED = (
    'Good morning, {name}. The morning routine is underway. I hope the coffee is ready.',
    'Morning, {name}. The house is waking up, and the pets are probably already supervising.',
    'Good morning, {name}. The morning routine is underway. Another day for us to manage, my bru.',
)

def morning_reply(name, profiles):
    """Use only trusted profile's local phrases, otherwise safe generic replies."""
    if not isinstance(name, str) or not name:
        return random.choice(NEUTRAL)
    profile = next((item for item in profiles.values() if isinstance(item, dict)
                    and item.get('name') == name), {}) if isinstance(profiles, dict) else {}
    phrases = profile.get('morning_responses')
    if isinstance(phrases, list):
        valid = [p.strip() for p in phrases if isinstance(p, str) and p.strip() and len(p) <= 500]
        if valid:
            return random.choice(valid).replace('{name}', name)
    return random.choice(NAMED).replace('{name}', name)
