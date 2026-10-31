"""Exact follow-up forms with no inferred target names."""
import re
from .text import percentages

def followup(text):
    text=percentages(text).lower().replace('’',"'").strip().rstrip('.?!')
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text)
    preview=False
    text=re.sub(r'^(?:(?:no[ ,]+)?actually[ ,]+|no[ ,]+i meant[ ,]+)', '', text)
    for prefix in ['preview ','dry run ','what would you do if i said ']:
        if text.startswith(prefix):preview=True;text=text[len(prefix):];break
    m=re.fullmatch(r'(?:please )?(?:turn|switch) (?:them|it) (?:back )?(on|off)(?: again)?(?: please)?',text)
    if m:return 'turn '+m[1]+' __previous_lights__',preview
    m=re.fullmatch(r'(?:please )?(?:turn|switch) (on|off) (?:them|it)(?: please)?',text)
    if m:return 'turn '+m[1]+' __previous_lights__',preview
    m=re.fullmatch(r'(?:please )?set (?:them|it) to (\d+(?:\.\d+)?) (?:percent|%)(?: please)?',text)
    if m:return 'set __previous_lights__ to '+m[1]+' percent',preview
    m=re.fullmatch(r'(?:make (?:them|it) |(?:a bit |a little )?)(brighter|dimmer)',text)
    if m:return ('brighten' if m[1]=='brighter' else 'dim')+' __previous_lights__',preview
    m=re.fullmatch(r'(dim|brighten) (?:them|it)',text)
    if m:return m[1]+' __previous_lights__',preview
    return None


def additional_room(text, previous_action):
    """Handle 'and the dining room lights' only after an established on/off action."""
    text=text.lower().replace('’', "'").strip().rstrip('.?!')
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+', '', text)
    match=re.fullmatch(r'and (?:the )?(.+)',text)
    if not match or previous_action not in {'turn_on','turn_off'}:
        return None
    target=match[1].strip()
    if not target or re.fullmatch(r'(?:it|them|that|those|these)(?: lights?)?', target):
        return None
    return 'turn '+previous_action.removeprefix('turn_')+' '+target


def followup_steps(hass, text, ids):
    """Revalidate all remembered light and explicitly mapped switch targets."""
    from .discovery import lighting
    from .named_switches import named_switch
    from .settings import get
    lights=[value for value in ids if value.startswith('light.')]
    switches=[value for value in ids if value.startswith('switch.')]
    if len(lights)+len(switches)!=len(ids):
        raise ValueError('Those targets are no longer available. Nothing was run.')
    toggle=re.fullmatch(r'turn (on|off) __previous_lights__',text)
    if switches and not toggle:
        raise ValueError('Some previous lights are switches and cannot be dimmed. Nothing was run.')
    steps=[]
    if lights:
        step=lighting(hass,text,lights)
        if step is None:raise ValueError('Please name the lights again. Nothing was run.')
        steps.append(step)
    mappings=get(hass,'switch_lights',{})
    for entity in switches:
        names=[name for name,target in mappings.items() if target==entity] if isinstance(mappings,dict) else []
        if not names:raise ValueError('A previous switch is no longer configured. Nothing was run.')
        step=named_switch(hass,'turn '+toggle[1]+' '+names[0])
        if step is None:raise ValueError('A previous switch is no longer available. Nothing was run.')
        steps.append(step)
    return steps
