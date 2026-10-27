"""Bounded media controls on Assist-exposed players."""
import re
from .discovery import norm, text_aliases
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.components.media_player import MediaPlayerEntityFeature as Feature


def media_plan(hass, text, area=None):
    text=norm(text)
    prefix=r'(?:please )?'
    suffix=r'(?: (?:on|in) (?:the )?(.+?))?(?: please)?'
    patterns=[(prefix+r'pause(?: (?:the )?music)?'+suffix,'media_pause',Feature.PAUSE),
              (prefix+r'(?:resume|continue)(?: (?:the )?music)?'+suffix,'media_play',Feature.PLAY),
              (prefix+r'(?:next track|next song|skip(?: (?:this|the) (?:track|song))?)'+suffix,'media_next_track',Feature.NEXT_TRACK)]
    action=None;target=None;volume=None;feature=None
    for pattern,service,flag in patterns:
        match=re.fullmatch(pattern,text)
        if match:action=service;target=match[1];feature=flag;break
    if not action:
        match=re.fullmatch(prefix+r'set (?:the )?volume(?: (?:on|in) (?:the )?(.+?))? to (\d+(?:\.\d+)?) (?:percent|%)'+r'(?: please)?',text)
        if not match:return None
        target,amount=match.groups();volume=float(amount)
        if not 0<=volume<=100:raise ValueError('Volume must be between zero and 100 percent. Nothing was run.')
        action='volume_set';feature=Feature.VOLUME_SET
    registry=er.async_get(hass);devices=dr.async_get(hass);areas=ar.async_get(hass)
    candidates=[]
    for state in hass.states.async_all('media_player'):
        if not async_should_expose(hass,'conversation',state.entity_id):continue
        entry=registry.async_get(state.entity_id)
        if entry and (entry.disabled_by or entry.hidden_by):continue
        area_id=entry.area_id if entry else None
        if not area_id and entry and entry.device_id:
            dev=devices.async_get(entry.device_id);area_id=dev.area_id if dev else None
        assigned=areas.async_get_area(area_id) if area_id else None
        names=text_aliases(state.name)|text_aliases(entry.aliases if entry else None)|{norm(state.entity_id)}
        if target:
            if target not in names and (assigned is None or target not in (text_aliases(assigned.name)|text_aliases(assigned.aliases))):continue
        elif area is not None and area_id!=area.id:continue
        candidates.append(state)
    if not candidates:raise ValueError('I could not find an Assist-exposed media player for that request. Nothing was run.')
    if len(candidates)>1:raise ValueError('Which media player? Please name one: '+', '.join(str(s.name) for s in candidates[:5])+'. Nothing was run.')
    state=candidates[0]
    if state.state in {'unknown','unavailable','off'}:raise ValueError(str(state.name)+' is unavailable or off. Nothing was run.')
    supported=state.attributes.get('supported_features',0)
    if not isinstance(supported,int) or not supported & int(feature):raise ValueError(str(state.name)+' does not report support for that action. Nothing was run.')
    data={'entity_id':state.entity_id}
    if volume is not None:data['volume_level']=volume/100
    return {'kind':'media_control','name':action,'data':data,'target_label':str(state.name),'label':action.replace('_',' ')+' on '+str(state.name)}
