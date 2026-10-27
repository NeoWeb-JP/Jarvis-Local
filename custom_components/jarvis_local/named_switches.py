"""Explicit switch-backed lighting names; never discover arbitrary sockets."""
import re
from .discovery import norm
from homeassistant.components.homeassistant.exposed_entities import async_should_expose

from .settings import get

def named_switch(hass,text):
    text=norm(text)
    patterns=[r'(?:please )?(?:turn|switch) (on|off) (?:the )?(.+?)(?: please)?',r'(?:please )?(?:(?:turn|switch) )?(?:the )?(.+?) (on|off)(?: please)?']
    m=re.fullmatch(patterns[0],text)
    if m:action,target=m[1],m[2]
    else:
        m=re.fullmatch(patterns[1],text)
        if not m:return None
        target,action=m[1],m[2]
    mappings=get(hass, "switch_lights", {})
    entity=mappings.get(target) if isinstance(mappings, dict) else None
    if not entity:return None
    state=hass.states.get(entity)
    if state is None or state.state not in {'on','off'}:
        raise ValueError(target.title() + ' is unavailable. Nothing was run.')
    if not async_should_expose(hass,'conversation',entity):
        raise ValueError('Expose ' + target + ' to Assist before using this command. Nothing was run.')
    return {'kind':'switch_light','name':'turn_'+action,'data':{'entity_id':[entity]},'target_label':target.title(),'label':'turn '+action+' '+target+' ('+entity+')'}
