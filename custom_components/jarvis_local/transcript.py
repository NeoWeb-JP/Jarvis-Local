"""Voice-only, inventory-grounded corrections for specific STT confusions."""
import re
from .discovery import lighting, inventory, norm, text_aliases
from .named_switches import named_switch
from homeassistant.helpers import entity_registry as er

def correct(hass, text, area=None):
    cleaned=norm(text)
    cleaned=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',cleaned)
    prefix=''
    for p in ['preview ','dry run ','what would you do if i said ']:
        if cleaned.startswith(p):prefix=p;cleaned=cleaned[len(p):];break
    candidate=re.sub(r'\blaunch (?=spotlights?\b)', 'lounge ', cleaned)
    changes=[]
    if candidate != cleaned:changes.append('launch spotlight -> lounge spotlight')
    comma_free=re.sub(r'(?<!\d)[,.]+(?!\d)', ' ', candidate)
    comma_free=re.sub(r'\s+', ' ', comma_free).strip()
    if comma_free != candidate:
        candidate=comma_free
        changes.append('removed punctuation between words')
    rooms,unassigned=inventory(hass)
    ids=set(unassigned) | {i for r in rooms.values() for i in r['lights']}
    registry=er.async_get(hass)
    names={}
    for entity in ids:
        state=hass.states.get(entity)
        entry=registry.async_get(entity)
        if state is None:continue
        for alias in text_aliases(state.name) | text_aliases(entry.aliases if entry else None):
            names.setdefault(alias,set()).add(entity)
    joined=split_joined(candidate,names)
    joined_ids=set()
    if joined != candidate:
        for alias, entity_ids in names.items():
            if re.fullmatch(r'(?:please )?(?:(?:turn|switch) )?(?:the )?'+re.escape(alias)+r'(?:on|off)(?: please)?',candidate):
                joined_ids.update(entity_ids)
        candidate=joined
        changes.append('separated exact light name and action')
    if re.search(r'\bof$', candidate):
        candidate=re.sub(r'\bof$', 'off', candidate)
        changes.append('trailing of -> off')
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
    try:
        from .planner import plan
        from .room_context import apply_room
        steps,preview=plan(hass,apply_room(candidate,area,hass),area)
    except ValueError:return text,[]
    if preview or not steps or any(step['kind'] not in {'light','switch_light'} or step['name'] not in {'turn_on','turn_off'} for step in steps):
        return text,[]
    if joined_ids and {entity for step in steps for entity in step.get('data',{}).get('entity_id',[])} != joined_ids:
        return text,[]
    return prefix+candidate,changes


def split_joined(text, names):
    """Split only a complete on/off command with one exact inventory name."""
    # Cancellation, corrections and compound requests must retain their meaning.
    if re.search(r"\b(?:no|not|never|stop|actually|cancel|don\x27t|do not|and|then|but|or)\b", text):
        return text
    matches=set()
    for alias, ids in names.items():
        if len(ids) != 1:
            continue
        pattern=r"((?:please )?(?:(?:turn|switch) )?(?:the )?)"+re.escape(alias)+r"(on|off)( please)?"
        match=re.fullmatch(pattern,text)
        if match:
            matches.add(match[1]+alias+" "+match[2]+(match[3] or ""))
    return next(iter(matches)) if len(matches)==1 else text
