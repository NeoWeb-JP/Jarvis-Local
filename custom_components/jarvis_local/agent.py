"""Bounded local agent with preflight validation and previews."""
import asyncio
import logging
from time import perf_counter, monotonic
from uuid import uuid4
from .settings import get
from .followup import followup
from .personality import confirmation
from .transcript import correct
from .verify import verify
from .discovery import lighting
from homeassistant.components import conversation
from homeassistant.helpers import intent
from homeassistant.exceptions import HomeAssistantError
from .planner import plan
from .status import answer
from .speech import recover_off
from .room_context import source_area, apply_room
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

class JarvisAgent(conversation.ConversationEntity):
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL
    _attr_name = 'Jarvis Local'
    _attr_unique_id = 'jarvis_local_test'

    def __init__(self, hass):
        self.hass = hass
        self._lock = asyncio.Lock()
        self._recent_lights = {}

    @property
    def supported_languages(self):
        return ['en']

    async def async_process(self, user_input):
        return await self.async_handle(user_input)

    async def async_handle(self, user_input, area_override=None):
        start = perf_counter()
        result = intent.IntentResponse(language=user_input.language)
        steps=[]
        preview=False
        area=None
        resolved_text=user_input.text
        outcome='rejected'
        failure=None
        conversation_id=user_input.conversation_id or uuid4().hex
        memory_key=(getattr(user_input.context,'user_id',None),conversation_id,getattr(user_input,'satellite_id',None) or getattr(user_input,'device_id',None),getattr(area_override,'id',None))
        now=monotonic()
        self._recent_lights={k:v for k,v in self._recent_lights.items() if now-v['at'] < 120}
        followup_used=False
        corrections=[]
        command_text=user_input.text
        try:
            area=area_override or source_area(self.hass,user_input)
            if getattr(user_input,'device_id',None) or getattr(user_input,'satellite_id',None):
                command_text,corrections=correct(self.hass,user_input.text)
            continuation=followup(command_text)
            if continuation is not None:
                previous=self._recent_lights.get(memory_key)
                if previous is None:
                    raise ValueError('Which lights do you mean? Please name the room or lights.')
                resolved_text,preview=continuation
                step=lighting(self.hass,resolved_text,previous['ids'])
                if step is None:raise ValueError('Please name the lights again.')
                steps=[step]
                followup_used=True
            else:
                resolved_text=apply_room(command_text,area,self.hass)
                steps, preview = plan(self.hass, resolved_text,area)
        except ValueError as err:
            recovered = recover_off(self.hass, user_input.text) if getattr(user_input, 'device_id', None) else None
            if recovered is not None:
                # Retry with the same context; never infer voice recovery from chat.
                from dataclasses import replace
                return await self.async_handle(replace(user_input, text=recovered),area_override)
            speech = str(err)
            failure=str(err)
        else:
            if preview:
                outcome='preview'
                speech = 'Preview only. I would ' + '; then '.join(s['label'] for s in steps) + '. No actions were run.'
            elif self._lock.locked():
                outcome='busy'
                speech = 'I am processing another request. Please try again shortly.'
            else:
                outcome='completed'
                replies = []
                async with self._lock:
                    try:
                        for step in steps:
                            if step['kind'] == 'text':
                                replies.append(step['response'])
                                continue
                            if step['kind'] == 'brightness':
                                unverified=[]
                                for call in step['calls']:
                                    await self.hass.services.async_call('light',call['service'],call['data'],blocking=True,context=user_input.context)
                                    unverified.extend(await verify(self.hass,'light',call['service'],call['data']))
                                step['unverified']=unverified
                                if unverified:
                                    replies.append('I sent the brightness request, but Home Assistant has not confirmed: '+', '.join(unverified)+'.')
                                    continue
                                replies.append(await confirmation(self.hass,user_input.context,'Adjusting '+step.get('target_label','the lights')+'.',action='brightness') if step['calls'] else 'Those lights are off, so I left them off.')
                                continue
                            if step['kind'] == 'switch_light':
                                await self.hass.services.async_call('switch',step['name'],step['data'],blocking=True,context=user_input.context)
                                unverified=await verify(self.hass,'switch',step['name'],step['data'])
                                step['unverified']=unverified
                                if unverified:
                                    replies.append('I sent the request, but Home Assistant has not confirmed the change.')
                                    continue
                                replies.append(await confirmation(self.hass,user_input.context,'Turning '+('off' if step['name']=='turn_off' else 'on')+' '+step.get('target_label', 'the light')+'.',action='off' if step['name']=='turn_off' else 'on'))
                                continue
                            if step['kind'] == 'light':
                                await self.hass.services.async_call('light', step['name'], step['data'], blocking=True, context=user_input.context)
                                unverified=await verify(self.hass,'light',step['name'],step['data'])
                                step['unverified']=unverified
                                if unverified:
                                    replies.append('I sent the command, but Home Assistant has not confirmed: '+', '.join(unverified)+'.')
                                    continue
                                replies.append(await confirmation(self.hass,user_input.context,'Turning '+('off' if step['name']=='turn_off' else 'on')+' '+step.get('target_label','the lights')+'.',action='off' if step['name']=='turn_off' else 'on'))
                                continue
                            if step['kind'] == 'guest':
                                data=step['data']; operation=data['operation']
                                if operation=='status':
                                    mode=self.hass.states.get(get(self.hass, 'guest_mode')).state
                                    names=self.hass.states.get(get(self.hass, 'guest_names')).state.strip()
                                    if mode=='off': replies.append('Guest Mode is off. Nobody is currently assigned.')
                                    elif not names: replies.append('Guest Mode is on, but no names are recorded.')
                                    else: replies.append('Guest Mode is on. In charge: '+names+'.')
                                elif operation=='set':
                                    await self.hass.services.async_call('input_text','set_value',{'entity_id':get(self.hass, 'guest_names'),'value':data['names']},blocking=True,context=user_input.context)
                                    await self.hass.services.async_call('input_boolean','turn_on',{'entity_id':get(self.hass, 'guest_mode')},blocking=True,context=user_input.context)
                                    replies.append('Guest Mode is on. In charge: '+data['names']+'.')
                                else:
                                    await self.hass.services.async_call('input_text','set_value',{'entity_id':get(self.hass, 'guest_names'),'value':''},blocking=True,context=user_input.context)
                                    await self.hass.services.async_call('input_boolean','turn_off',{'entity_id':get(self.hass, 'guest_mode')},blocking=True,context=user_input.context)
                                    replies.append('Guest Mode is off and the names are cleared.')
                                continue
                            if step['kind'] == 'music':
                                await self.hass.services.async_call('script',step['name'],step['data'],blocking=True,context=user_input.context)
                                replies.append('I requested '+step['data']['music']+' in '+step['data']['location']+'.')
                                continue
                            if step['kind'] == 'status':
                                replies.append(answer(self.hass, step['text']))
                                continue
                            reply = await self.hass.services.async_call(
                                'script', step['name'], step['data'], blocking=True,
                                return_response=True, context=user_input.context)
                            if (reply or {}).get('response'):
                                routine_reply=reply['response']
                                if step['name']=='jarvis_local_good_morning' and isinstance(routine_reply,str) and len(routine_reply.split())<9:
                                    routine_reply=await confirmation(self.hass,user_input.context,routine_reply,action='morning')
                                replies.append(routine_reply)
                    except (HomeAssistantError, ValueError) as err:
                        outcome='failed'
                        failure=str(err)
                        _LOGGER.exception('Jarvis routine failed')
                        replies.append('I stopped because an action failed. Earlier actions may already have run. Please check the Home Assistant log before retrying.')
                speech = ' '.join(r for r in replies if r)
                if outcome=='completed':
                    for step in steps:
                        if step['kind']=='light' and not step.get('unverified'):
                            self._recent_lights[memory_key]={'at':monotonic(),'ids':list(step['data']['entity_id'])}
                        elif step['kind']=='brightness' and step['calls'] and not step.get('unverified'):
                            self._recent_lights[memory_key]={'at':monotonic(),'ids':list(dict.fromkeys(i for call in step['calls'] for i in call['data']['entity_id']))}
                        elif step['kind'] in {'action','switch_light','guest'}:
                            self._recent_lights.pop(memory_key,None)
                    while len(self._recent_lights)>64:
                        del self._recent_lights[next(iter(self._recent_lights))]
        if getattr(user_input,'device_id',None) or getattr(user_input,'satellite_id',None):
            speech=speech.replace(' Try "help" for supported requests.', '')
        record = {
            'time':datetime.now(timezone.utc).isoformat(),
            'received_text':user_input.text,'resolved_text':resolved_text,'transcript_corrections':corrections,
            'device_id':getattr(user_input,'device_id',None),
            'satellite_id':getattr(user_input,'satellite_id',None),
            'area':area.name if area else None,'preview':preview,
            'steps':steps,'outcome':outcome,'error':failure,'followup_used':followup_used,
            'response':speech,'elapsed_ms':round((perf_counter()-start)*1000),
        }
        history=self.hass.data.setdefault('jarvis_local',{}).setdefault('diagnostics',[])
        history.append(record)
        del history[:-20]
        result.async_set_speech(speech)
        _LOGGER.info('Jarvis local processing: %.0f ms', (perf_counter()-start)*1000)
        return conversation.ConversationResult(response=result, conversation_id=conversation_id)
