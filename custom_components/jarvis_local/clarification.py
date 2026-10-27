"""Bounded, conversation-scoped clarification for a single light command."""
import re
from .discovery import inventory, norm, display_name, text_aliases
from homeassistant.helpers import entity_registry as er


def request(hass, text, area):
    text=norm(text)
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text)
    preview=False
    for prefix in ('preview ', 'dry run ', 'what would you do if i said '):
        if text.startswith(prefix):preview=True;text=text[len(prefix):];break
    match=re.fullmatch(r'(?:please )?(?:turn|switch) (on|off) (?:the )?(.+?)(?: please)?',text)
    if match:action,target=match.groups()
    else:
        match=re.fullmatch(r'(?:please )?(?:(?:turn|switch) )?(?:the )?(.+?) (on|off)(?: please)?',text)
        if not match:return None
        target,action=match.groups()
    if ' and ' in target or not target:return None
    rooms,unassigned=inventory(hass)
    registry=er.async_get(hass)
    if area is not None:
        scope=rooms.get(area.id,{}).get('lights',[])
    else:
        scope=list(unassigned)+[i for room in rooms.values() for i in room['lights']]
    matches=[]
    for entity_id in sorted(set(scope)):
        state=hass.states.get(entity_id)
        if state is None:continue
        entry=registry.async_get(entity_id)
        names=text_aliases(state.name)|text_aliases(entry.aliases if entry else None)
        words=set(norm(display_name(state)).split())
        if target in names or (target=='lamp' and 'lamp' in words):
            room=next((r['name'] for r in rooms.values() if entity_id in r['lights']),None)
            matches.append({'id':entity_id,'name':display_name(state),'room':room})
    if len(matches)<2:return None
    options=[item['name']+(' in '+item['room'] if item['room'] else '') for item in matches]
    return {'action':action,'preview':preview,'matches':matches,'question':'Which light did you mean: '+', '.join(options[:5])+'?'}


def resolve(pending, text):
    answer=norm(text)
    if answer in {'cancel','cancel that','never mind','nevermind'}:return 'cancel',None
    answer=re.sub(r'^(?:the |in the |in )','',answer)
    answer=re.sub(r' (?:one|light|please)$','',answer).strip()
    found=[]
    for item in pending['matches']:
        name=norm(item['name']);room=norm(item['room'])
        if answer and (answer==name or answer==room or (answer+' lamp')==name or (room and answer+' room'==room) or answer==norm(item['id'])):
            found.append(item['id'])
    if len(found)==1:return 'resolved',found[0]
    return 'unclear',None
