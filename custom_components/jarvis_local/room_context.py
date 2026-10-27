"""Resolve only explicitly roomless lighting phrases."""
import re
from .text import percentages
from .discovery import inventory, norm, display_name
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

def source_area(hass, user_input):
    device_id=getattr(user_input,'device_id',None)
    satellite=getattr(user_input,'satellite_id',None)
    if satellite:
        entry=er.async_get(hass).async_get(satellite)
        if entry:
            if entry.area_id:return ar.async_get(hass).async_get_area(entry.area_id)
            device_id=entry.device_id or device_id
    device=dr.async_get(hass).async_get(device_id) if device_id else None
    return ar.async_get(hass).async_get_area(device.area_id) if device and device.area_id else None

def short_room_target(hass, area, clause):
    if hass is None or area is None:return clause
    patterns=[
        r'(set (?:the )?)(.+?)( to \d+(?:\.\d+)? percent)',
        r'((?:dim|brighten) (?:the )?)(.+?)()',
        r'((?:turn|switch) (?:on|off) (?:the )?)(.+?)()',
        r'((?:(?:turn|switch) )?(?:the )?)(.+?)( (?:on|off))',
    ]
    match=next((m for pattern in patterns if (m:=re.fullmatch(pattern,clause))),None)
    if match is None:return clause
    target=norm(match[2])
    rooms,_=inventory(hass)
    # Bedroom is a source-relative shorthand only if no literal Bedroom area exists.
    if target in {'bedroom light','bedroom lights'} and norm(area.name).endswith('bedroom'):
        if not any(norm(r['name'])=='bedroom' for r in rooms.values()):
            return match[1]+area.name+' lights'+match[3]
    if target not in {'fan light','ceiling light','lamp'}:return clause
    words=set(target.split())
    candidates=[]
    for entity in rooms.get(area.id,{}).get('lights',[]):
        state=hass.states.get(entity)
        name_words=set(norm(display_name(state)).split())
        id_words=set(entity.split('.',1)[1].split('_'))
        if words.issubset(name_words) or words.issubset(id_words):candidates.append(entity)
    if len(candidates)!=1:
        raise ValueError('Please use the full light name. I could not identify one '+target+' in '+area.name+'. Nothing was run.')
    return match[1]+candidates[0]+match[3]

def apply_room(text, area, hass=None):
    text=percentages(text).replace('’',"'").strip()
    # Guest names need their original spelling; the guest parser is case-insensitive.
    if re.search(r'\b(?:in charge|looking after the house|guests have left)\b',text,re.I):return text
    text=text.lower()
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text)
    prefix=''
    for candidate in ['preview ','dry run ','what would you do if i said ']:
        if text.startswith(candidate):prefix=candidate;text=text[len(candidate):];break
    clauses=re.split(r'(\s+(?:and then|then|and)\s+|\s*;\s*)',text)
    for index in range(0,len(clauses),2):
        clause=clauses[index].strip().rstrip('.?!')
        updated=short_room_target(hass,area,clause)
        if updated!=clause:
            clauses[index]=updated
            continue
        # Bare lamp refers only to a unique lamp in the source room.
        if re.fullmatch(r'(?:(?:turn|switch) )?(?:on|off) (?:the )?lamp|(?:(?:turn|switch) )?(?:the )?lamp (?:on|off)',clause):
            if area is None or hass is None:raise ValueError('Which lamp? Please name the room or the lamp. Nothing was run.')
            rooms,_=inventory(hass)
            candidates=[i for i in rooms.get(area.id,{}).get('lights',[]) if 'lamp' in norm(display_name(hass.states.get(i))).split()]
            if len(candidates)!=1:raise ValueError('I could not identify one lamp in '+area.name+'. Please use its full name. Nothing was run.')
            lamp_name=candidates[0]
            clauses[index]=re.sub(r'\blamp\b',lambda _:lamp_name,clause)
            continue
        action=None
        m=re.fullmatch(r'(?:please )?(?:(?:turn|switch) )?(on|off) (?:the )?lights?(?: please)?',clause)
        if m:action=('toggle',m[1])
        m=re.fullmatch(r'(?:please )?(?:(?:turn|switch) )?(?:the )?lights? (on|off)(?: please)?',clause)
        if m:action=('toggle',m[1])
        m=re.fullmatch(r'(?:please )?(dim|brighten) (?:the )?lights?(?: please)?',clause)
        if m:action=('relative',m[1])
        m=re.fullmatch(r'(?:please )?set (?:the )?lights? to (\d+(?:\.\d+)?) (percent|%)(?: please)?',clause)
        if m:action=('brightness',m[1])
        if re.fullmatch(r'(?:are|is) (?:the )?lights? (?:on|off)',clause):action=('status','')
        if action is None:continue
        if area is None:raise ValueError('Which room? Assign this Muse to an area, select a chat room, or name the room in your command. Nothing was run.')
        kind,value=action
        clauses[index]={'toggle':f'turn {value} the {area.name} lights','relative':f'{value} the {area.name} lights','brightness':f'set the {area.name} lights to {value} percent','status':f'are the {area.name} lights on'}[kind]
    return prefix+''.join(clauses)
