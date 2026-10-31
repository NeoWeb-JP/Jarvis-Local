"""Live light inventory using HA area/device/entity assignments."""
import re
from .text import percentages
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.components.homeassistant.exposed_entities import async_should_expose

def norm(text):
    if not isinstance(text, str):
        return ''
    text = re.sub(r'\s+', ' ', percentages(text).lower().strip().rstrip('.?!'))
    return re.sub(r'\bspot lights?\b', lambda m: 'spotlights' if m[0].endswith('lights') else 'spotlight', text)

def text_aliases(value):
    """Ignore internal computed-name markers and malformed alias values."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    return {normal for item in value if (normal := norm(item))}

def display_name(state):
    name = state.name
    return name if isinstance(name, str) and name.strip() else state.entity_id.split('.', 1)[-1].replace('_', ' ').title()

def inventory(hass):
    areas = ar.async_get(hass)
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    rooms = {a.id: {'name':a.name, 'aliases':(text_aliases(a.name) | text_aliases(a.aliases)), 'lights':[]} for a in areas.async_list_areas()}
    unassigned=[]
    for state in hass.states.async_all('light'):
        if not async_should_expose(hass, 'conversation', state.entity_id):continue
        entry=entities.async_get(state.entity_id)
        if entry and (entry.disabled_by or entry.hidden_by):continue
        area_id=entry.area_id if entry else None
        if not area_id and entry and entry.device_id:
            device=devices.async_get(entry.device_id)
            area_id=device.area_id if device else None
        if area_id in rooms:rooms[area_id]['lights'].append(state.entity_id)
        else:unassigned.append(state.entity_id)
    return rooms,unassigned

def _lighting(hass, text, previous=None):
    text=norm(text)
    rooms,unassigned=inventory(hass)
    all_ids=sorted({i for r in rooms.values() for i in r['lights']} | set(unassigned))
    if text in {'discover lights','list lights','list rooms','list areas','list zones'}:
        if text=='list zones':
            return {'kind':'text','response':'Geographic presence zones: '+(', '.join(display_name(s) for s in hass.states.async_all('zone')) or 'none')+'.', 'label':'list geographic zones'}
        lines=[r['name']+': '+(', '.join(display_name(hass.states.get(i)) for i in r['lights']) or 'no exposed lights') for r in rooms.values()]
        if unassigned:lines.append('No assigned area: '+', '.join(display_name(hass.states.get(i)) for i in unassigned))
        return {'kind':'text','response':'; '.join(lines) or 'No lights discovered.', 'label':'list discovered lights and areas'}
    area_scope=False
    def resolve(target):
        nonlocal area_scope
        if target == '__previous_lights__' and previous:
            ids=list(previous)
            if not set(ids).issubset(all_ids):
                raise ValueError('Those lights are no longer available to Assist. Please name the lights again. Nothing was run.')
            return ids, ', '.join(display_name(hass.states.get(i)) for i in ids)
        target=norm(target)
        room_match=re.fullmatch(r'__room_spotlights_(.+)__',target)
        if room_match:
            room=rooms.get(room_match[1])
            if room is None:raise ValueError('That area is no longer available. Nothing was run.')
            registry=er.async_get(hass)
            ids=[]
            for entity_id in room['lights']:
                state=hass.states.get(entity_id);entry=registry.async_get(entity_id)
                aliases=text_aliases(state.name) | text_aliases(entry.aliases if entry else None) | {norm(entity_id.replace('_',' '))}
                if any(re.search(r'\bspotlights?\b',name) for name in aliases):ids.append(entity_id)
            if not ids:raise ValueError('I could not find any exposed spotlights in '+room['name']+'. Nothing was run.')
            return sorted(ids),room['name']+' spotlights'
        target=re.sub(r'^the ', '', target)
        target=re.sub(r'^lights? in (?:the )?', '', target)
        area_target=re.sub(r' lights?$', '', target)
        matches=[r for r in rooms.values() if area_target in r['aliases']]
        named=[]
        registry=er.async_get(hass)
        for entity_id in all_ids:
            state=hass.states.get(entity_id);entry=registry.async_get(entity_id)
            aliases = text_aliases(state.name) | text_aliases(entry.aliases if entry else None) | {norm(entity_id)}
            if target in aliases:named.append(entity_id)
        exact_rooms = [r for r in rooms.values() if area_target == norm(r['name'])]
        if len(exact_rooms) > 1:
            raise ValueError('More than one area has that name. Use a unique area name. Nothing was run.')
        if exact_rooms:
            area_scope=True
            ids = sorted(exact_rooms[0]['lights'])
            label = exact_rooms[0]['name']
        elif len(named) == 1:
            ids = named
            label = display_name(hass.states.get(named[0]))
        elif len(named) > 1:
            options=[]
            for entity_id in named:
                state=hass.states.get(entity_id)
                room=next((room['name'] for room in rooms.values() if entity_id in room['lights']), None)
                option=display_name(state) + (' in '+room if room else '')
                if option in options: option += ' (another device with the same name)'
                options.append(option)
            raise ValueError('Which light did you mean: '+', '.join(options[:5])+'? Please repeat your command with its full name. Nothing was run.')
        elif not matches:
            # Exact numbered entity-ID families form a subgroup; no fuzzy matching.
            families = {}
            for entity_id in all_ids:
                local_id = entity_id.split('.', 1)[1]
                family = re.sub(r'_(?:light_)?\d+$', '', local_id)
                if family != local_id:
                    family_name = norm(family.replace('_', ' '))
                    families.setdefault(family_name, []).append(entity_id)
            group = families.get(target, [])
            if not group and target.endswith(' spotlight'):
                group = families.get(target+'s', [])
            if len(group) < 2:
                raise LookupError(target)
            # A family spanning multiple areas is ambiguous rather than a house-wide group.
            group_areas = {area_id for area_id, room in rooms.items() if set(group) & set(room['lights'])}
            if len(group_areas) != 1 or not set(group).issubset(rooms[next(iter(group_areas))]['lights']):
                raise ValueError('That numbered light family is not assigned to one area. Nothing was run.')
            ids = sorted(group)
            label = target
        elif len(matches) == 1:
            area_scope=True
            ids = sorted(matches[0]['lights'])
            label = matches[0]['name']
        elif len(matches) > 1:
            raise ValueError('More than one area has that alias. Use its full name. Nothing was run.')
        else:
            raise LookupError(target)
        if not ids:raise ValueError('No exposed lights are assigned to '+label+'. Nothing was run.')
        return ids,label
    def status(ids,label):
        on=[];off=[];missing=[]
        for i in ids:
            state=hass.states.get(i)
            if state is None or state.state not in {'on','off'}:missing.append(i)
            elif state.state=='on':on.append(display_name(state))
            else:off.append(display_name(state))
        parts=[label+': '+str(len(on))+' on, '+str(len(off))+' off.']
        if on:parts.append('On: '+', '.join(on)+'.')
        if missing:parts.append('Unavailable or unknown: '+', '.join(missing)+'.')
        return {'kind':'text','response':' '.join(parts),'label':'check '+label}
    if text in {'which lights are on','what lights are on','are the lights on'}:
        return status(all_ids,'Discovered lights')
    m=re.fullmatch(r'(?:what|which) lights are in (?:the )?(.+)',text)
    if m:
        ids,label=resolve(m[1]);return {'kind':'text','response':label+': '+', '.join(display_name(hass.states.get(i)) for i in ids)+'.','label':'list lights in '+label}
    m=re.fullmatch(r'(?:are|is) (?:the )?(.+?) (on|off)',text)
    if m:
        ids,label=resolve(m[1]);return status(ids,label)
    action=None;value=None;target=None
    m=re.fullmatch(r'(?:please )?(?:turn|switch) (on|off) (?:the )?(.+?)(?: please)?',text)
    if m:action='turn_'+m[1];target=m[2]
    if not m:
        m=re.fullmatch(r'(?:please )?(?:turn|switch) (?:the )?(.+?) (on|off)(?: please)?',text)
        if m:target=m[1];action='turn_'+m[2]
    if not action:
        # Short spoken forms: office light off, kitchen on.
        m=re.fullmatch(r'(?:please )?(?:the )?(.+?) (on|off)(?: please)?',text)
        if m:target=m[1];action='turn_'+m[2]
    if not action:
        m=re.fullmatch(r'(?:please )?set (?:the )?(.+?) to (\d+(?:\.\d+)?) (?:percent|%)(?: please)?',text)
        if m:target=m[1];value=float(m[2]);action='brightness'
    if not action:
        m=re.fullmatch(r'(?:please )?(dim|brighten) (?:the )?(.+?)(?: please)?',text)
        if m:target=m[2];action=m[1]
    if action is None:return None
    ids,label=resolve(target)
    bad=[i for i in ids if hass.states.get(i) is None or hass.states.get(i).state not in {'on','off'}]
    if bad:raise ValueError('Some target lights are unavailable: '+', '.join(display_name(hass.states.get(i)) if hass.states.get(i) else i.split('.',1)[-1].replace('_',' ').title() for i in bad)+'. Nothing was run.')
    if action.startswith('turn_'):
        return {'kind':'light','target_label':label,'name':action,'data':{'entity_id':ids},'label':action.replace('_',' ')+' '+label}
    if value is not None and not 0<=value<=100:raise ValueError('Brightness must be between zero and 100 percent. Nothing was run.')
    calls=[]
    skipped=[]
    dimmable_count=0
    for i in ids:
        state=hass.states.get(i)
        modes=set(state.attributes.get('supported_color_modes') or [])
        if not modes.intersection({'brightness','color_temp','hs','xy','rgb','rgbw','rgbww','white'}):
            if area_scope:
                skipped.append(display_name(state))
                continue
            raise ValueError(display_name(state)+' does not report brightness support. Nothing was run.')
        dimmable_count+=1
        if action in {'dim','brighten'}:
            if state.state=='off':continue
            current=state.attributes.get('brightness')
            if not isinstance(current,(int,float)) or not 0<=current<=255:
                raise ValueError('Brightness is unknown for '+display_name(state)+'. Nothing was run.')
            percent=max(0,min(100,round(current/255*100)+(20 if action=='brighten' else -20)))
        else:percent=value
        calls.append({'service':'turn_off' if percent==0 else 'turn_on','data':{'entity_id':[i], **({'brightness_pct':percent} if percent else {})}})
    if dimmable_count==0:
        raise ValueError('No dimmable lights were found in '+label+'. Nothing was run.')
    return {'kind':'brightness','skipped_non_dimmable':skipped,'target_label':label,'calls':calls,'label':action+' '+label+(' to '+str(value)+' percent' if value is not None else ' by 20 percentage points, leaving off lights off')+'; targets: '+', '.join(display_name(hass.states.get(i)) for call in calls for i in call['data']['entity_id'])+('; leave unchanged (not dimmable): '+', '.join(skipped) if skipped else '')}

def lighting(hass, text, previous=None):
    try:
        return _lighting(hass, text, previous)
    except LookupError:
        return None
