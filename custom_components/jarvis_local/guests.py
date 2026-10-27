"""Explicit guest handover phrases using existing HA helpers."""
import re
from .settings import get

def recognize(text):
    text=text.strip().rstrip('.!?').strip()
    if re.fullmatch(r'(?:who is in charge|who is looking after the house)',text,re.I):return {'operation':'status'}
    if re.fullmatch(r'(?:the guests have left|our guests have left|clear the guests in charge)',text,re.I):return {'operation':'clear'}
    patterns=[r'put (.+?) in charge',r'we are going out and (.+?) (?:are|is) in charge',r'we are going out and leaving (.+?) in charge']
    for pattern in patterns:
        match=re.fullmatch(pattern,text,re.I)
        if match:
            names=match[1].strip()
            # Restrict to names and punctuation, avoiding accidental embedded commands.
            if not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .,'’&-]{0,254}",names):raise ValueError('I could not safely identify those names. Nothing was changed.')
            if re.search(r'\b(?:turn|switch|delete|unlock|open|close|set|clear|stop|start)\b',names,re.I):raise ValueError('The guest names were unclear. Nothing was changed.')
            return {'operation':'set','names':names}
    return None

def build(hass, data):
    mode_id=get(hass, 'guest_mode'); names_id=get(hass, 'guest_names')
    if not (isinstance(mode_id, str) and mode_id.startswith('input_boolean.') and isinstance(names_id, str) and names_id.startswith('input_text.')):
        raise ValueError('Guest helpers are not configured. Nothing was changed.')
    mode=hass.states.get(mode_id);names=hass.states.get(names_id)
    if not mode or mode.state not in {'on','off'} or not names or names.state in {'unknown','unavailable'}:
        raise ValueError('Guest Mode or the guest names helper is unavailable. Nothing was changed.')
    if data['operation']=='set':
        maxlen=names.attributes.get('max',255)
        if len(data['names'])>maxlen:raise ValueError('The guest names are too long for the helper. Nothing was changed.')
    label={'status':'check who is in charge','clear':'clear guests and turn off Guest Mode','set':'assign '+data.get('names','')+' and turn on Guest Mode'}[data['operation']]
    return {'kind':'guest','data':data,'label':label}
