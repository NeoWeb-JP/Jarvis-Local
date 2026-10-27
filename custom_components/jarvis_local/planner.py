"""Validate complete requests before any household action."""
import re
from .settings import get
from .parser import parse
from .status import answer
from .discovery import lighting
from .named_switches import named_switch
from .room_context import apply_room
from .guests import recognize as guest_recognize, build as guest_build

LABELS = {
    'jarvis_local_good_morning': 'run the morning routine',
    'jarvis_local_good_night': 'run the bedtime routine and announce in the bedroom',
    'jarvis_local_movie': 'request movie mode',
}

def plan(hass, text, area=None):
    raw_text = text.replace('’', "'").strip()
    raw_text = re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+', '', raw_text, flags=re.I)
    text = text.lower().replace('’', "'").strip()
    text = re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+', '', text)
    preview = False
    for prefix in ('what would you do if i said ', 'preview ', 'dry run '):
        if text.startswith(prefix):
            preview = True
            text = text[len(prefix):].strip()
            break
    text = text.strip(' "\'')
    guest_text = raw_text
    if preview:
        guest_text = re.sub(r'^(?:what would you do if i said |preview |dry run )', '', guest_text, flags=re.I)
    guest = guest_recognize(guest_text)
    if guest is not None:
        return [guest_build(hass,guest)],preview
    # Recognise a complete area name first, including names containing 'and'.
    whole = lighting(hass, text) or named_switch(hass,text)
    if whole is not None:
        return [whole], preview
    if re.fullmatch(r'[a-z][a-z ]+ (?:1|one)[.!?]?', text):
        raise ValueError('I heard a name followed by one, but no clear action. Please repeat with switch on or switch off. Nothing was run.')
    # Shared on/off applies to each complete target; validate all before execution.
    sentence = text.rstrip('.?!')
    match = re.fullmatch(r'(?:(?:turn|switch) )?(?:the )?(.+?) and (?:the )?(.+?) (on|off)', sentence)
    if match:
        target_a,target_b,action=match.groups()
    else:
        leading=re.fullmatch(r'(?:turn|switch) (on|off) (?:the )?(.+?) and (?:the )?(.+)',sentence)
        if leading:
            action,target_a,target_b=leading.groups()
            match=leading
    if match:
        parsed=[]
        for target in [target_a,target_b]:
            expanded=apply_room('turn '+action+' the '+target,area,hass)
            step=lighting(hass,expanded) or named_switch(hass,expanded)
            if not step or step['kind'] not in {'light','switch_light'}:
                raise ValueError('I could not identify '+target+'. Nothing was run.')
            parsed.append(step)
        return parsed,preview
    # Bounded playback requests use the user's existing Alexa music script.
    match=re.fullmatch(r'play (.+?)(?: (?:in|on) (?:the )?(kitchen|office|bedroom|upstairs|everywhere))?',sentence)
    if match:
        music,location=match.groups()
        script_id=get(hass, 'music_script')
        entity=hass.states.get(script_id) if isinstance(script_id, str) and script_id.startswith('script.') else None
        if entity is None or entity.state in {'unknown','unavailable'}:
            raise ValueError('The music control script is unavailable. Nothing was run.')
        return [{'kind':'music','name':script_id.split('.', 1)[1],'data':{'music':music,'location':location or 'everywhere'},'label':'request '+music+' in '+(location or 'everywhere')}],preview
    parts = re.split(r'\s+(?:and then|then|and)\s+|\s*;\s*', text)
    if not 1 <= len(parts) <= 4 or any(not p.strip() for p in parts):
        raise ValueError('Please use between one and four supported requests. Nothing was run.')
    steps = []
    for part in parts:
        light_step = lighting(hass, part) or named_switch(hass,part)
        if light_step is not None:
            steps.append(light_step)
            continue
        command = parse(part)
        if command is not None:
            name, data = command
            entity = hass.states.get('script.' + name)
            if entity is None or entity.state in {'unknown', 'unavailable'}:
                raise ValueError('A required shared routine is unavailable. Nothing was run.')
            if entity.state == 'on':
                raise ValueError('A requested routine is already running. Nothing was run.')
            label = LABELS[name]
            if name.endswith('movie'):
                label += ': ' + data['requested_action']
            steps.append({'kind':'action', 'name':name, 'data':data, 'label':label})
        elif answer(hass, part) is not None:
            steps.append({'kind':'status', 'text':part, 'label':'answer: ' + part})
        else:
            raise ValueError('I did not understand "' + part + '". Nothing was run. Try "help" for supported requests.')
    # Existing movie routines launch asynchronously and bedtime has broad effects.
    # Do not allow overlapping or conflicting routine combinations yet.
    if sum(s['kind'] in {'action','light','brightness','switch_light'} for s in steps) > 1:
        raise ValueError('For now, combine one household routine with status questions. Multiple routines must be requested separately. Nothing was run.')
    return steps, preview
