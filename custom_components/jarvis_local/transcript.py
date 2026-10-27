"""Voice-only, inventory-grounded corrections for specific STT confusions."""
import re
from .discovery import lighting, inventory, norm, text_aliases
from .named_switches import named_switch
from homeassistant.helpers import entity_registry as er

def correct(hass, text):
    cleaned=norm(text)
    cleaned=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',cleaned)
    prefix=''
    for p in ['preview ','dry run ','what would you do if i said ']:
        if cleaned.startswith(p):prefix=p;cleaned=cleaned[len(p):];break
    candidate=re.sub(r'\blaunch (?=spotlights?\b)', 'lounge ', cleaned)
    changes=[]
    if candidate!=cleaned:changes.append('launch spotlight -> lounge spotlight')
    m=re.fullmatch(r'(.+?) (?:1|one)',candidate)
    if m:
        # Do not reinterpret an actual numbered light name as a command.
        rooms,unassigned=inventory(hass)
        ids=set(unassigned) | {i for r in rooms.values() for i in r['lights']}
        registry=er.async_get(hass)
        for entity in ids:
            state=hass.states.get(entity);entry=registry.async_get(entity)
            if candidate in (text_aliases(state.name) | text_aliases(entry.aliases if entry else None)):
                return text,[]
        candidate=m[1]+' on'
        changes.append('trailing 1/one -> on')
    if not changes:return text,[]
    # Only known on/off lighting actions may benefit from these corrections.
    try:step=lighting(hass,candidate) or named_switch(hass,candidate)
    except ValueError:return text,[]
    if not step or step['kind'] not in {'light','switch_light'} or step['name'] not in {'turn_on','turn_off'}:
        return text,[]
    return prefix+candidate,changes
