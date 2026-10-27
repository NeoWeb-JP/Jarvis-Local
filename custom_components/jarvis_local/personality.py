"""Expanded lighting replies using the existing engine's effective personality."""
import json
import logging
import random
from collections import deque
from pathlib import Path
from homeassistant.exceptions import HomeAssistantError
from .settings import get
_LOGGER=logging.getLogger(__name__)
CATALOG=None

def choose(hass,mode,action,catalog):
    pools=catalog[mode]
    pool=list(dict.fromkeys(pools.get(action,[]) or pools['general']))
    history=hass.data.setdefault('jarvis_local',{}).setdefault('reply_history',{}).setdefault(mode,deque(maxlen=8))
    available=[line for line in pool if line not in history] or pool
    line=random.choice(available)
    history.append(line)
    return line

async def confirmation(hass, context, fallback, action='general'):
    global CATALOG
    script_id=get(hass, 'personality_script')
    state=hass.states.get(script_id) if isinstance(script_id, str) and script_id.startswith('script.') else None
    if state is None or state.state in {'unknown','unavailable'}:return fallback
    try:
        reply=await hass.services.async_call('script',script_id.split('.', 1)[1],
            {'response_context':'general'},blocking=True,return_response=True,context=context)
        if not isinstance(reply,dict):return fallback
        mode=reply.get('personality')
        if mode not in {'Classic','Sassy','Savage','Guest','Night'}:
            response=reply.get('response')
            return response.strip() if isinstance(response,str) and response.strip() else fallback
        if CATALOG is None:
            CATALOG=await hass.async_add_executor_job(lambda:json.loads(Path(__file__).with_name('responses.json').read_text()))
        if mode not in CATALOG:
            response=reply.get('response')
            return response.strip() if isinstance(response,str) and response.strip() else fallback
        line=choose(hass,mode,action,CATALOG)
        phonetic_id=get(hass, 'phonetic_script')
        phonetic=hass.states.get(phonetic_id) if isinstance(phonetic_id, str) and phonetic_id.startswith('script.') else None
        if phonetic and phonetic.state not in {'unknown','unavailable'}:
            try:
                converted=await hass.services.async_call('script',phonetic_id.split('.', 1)[1],
                    {'input_text':line},blocking=True,return_response=True,context=context)
                value=converted.get('text') if isinstance(converted,dict) else None
                if isinstance(value,str) and value.strip():return value.strip()
            except (HomeAssistantError,ValueError,TypeError):
                _LOGGER.debug('Phonetic conversion failed; using original lighting reply',exc_info=True)
        return line
    except (HomeAssistantError,ValueError,TypeError,OSError):
        _LOGGER.warning('Jarvis personality reply unavailable; using plain confirmation',exc_info=True)
    return fallback
