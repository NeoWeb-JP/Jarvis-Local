"""Small local conversational replies with optional speaker names."""
import random
import re

POOLS = {
    'thanks': ('You are welcome{address}. Happy to help.', 'A pleasure{address}. That is what I am here for.', 'Any time{address}. Somebody has to keep things running.'),
    'hello': ('Hello{address}. How can I help?', 'Hello{address}. I am ready when you are.', 'Hi{address}. What can I do for you?'),
}

def social_reply(text, name, history):
    text=re.sub(r'^(?:hey[ ,]+)?jarvis[ ,:]+', '', str(text).lower().strip()).strip(' .?!')
    if text in {'thank you','thanks','thanks jarvis','thank you jarvis','cheers'}:kind='thanks'
    elif text in {'hello','hi','hello jarvis','hi jarvis'}:kind='hello'
    else:return None
    key=(kind,name or '')
    pool=POOLS[kind]
    available=[item for item in pool if item!=history.get(key)] or pool
    chosen=random.choice(available);history[key]=chosen
    return chosen.replace('{address}', ', '+name if name else '')
