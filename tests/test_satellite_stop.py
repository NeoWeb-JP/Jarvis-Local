"""Stop regressions runnable without a Home Assistant installation."""
import ast
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock
from time import monotonic, perf_counter

ROOT=Path(__file__).resolve().parents[1]/'custom_components'/'jarvis_local'
errors=types.ModuleType('homeassistant.exceptions')
errors.HomeAssistantError=type('HomeAssistantError',(Exception,),{})
errors=sys.modules.setdefault('homeassistant.exceptions',errors)
spec=importlib.util.spec_from_file_location('satellite_stop',ROOT/'satellite_stop.py')
stop=importlib.util.module_from_spec(spec)
spec.loader.exec_module(stop)

def immediate(fn):
    def run(self):
        coroutine=fn(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        raise AssertionError('Mocked stop unexpectedly suspended')
    return run

class Stops(unittest.TestCase):
    @immediate
    async def test_mapping_and_phrase_isolation(self):
        for phrase in ('Stop','Be quiet','Shut up','Jarvis, shut up!','no stop'):
            self.assertTrue(stop.is_spoken_stop(phrase))
        for phrase in ('stop music in kitchen','stop kitchen timer','preview stop','cancel'):
            self.assertFalse(stop.is_spoken_stop(phrase))
        call=AsyncMock()
        hass=types.SimpleNamespace(data={'jarvis_local':{'settings':{
            'satellite_media_players':{'assist_satellite.bedroom':'media_player.bedroom',
                                      'assist_satellite.kitchen':'media_player.kitchen'}}}},
            services=types.SimpleNamespace(async_call=call))
        context=object()
        for satellite in ('assist_satellite.bedroom','assist_satellite.kitchen',None,'assist_satellite.unknown'):
            call.reset_mock()
            await stop.stop_player(hass,types.SimpleNamespace(satellite_id=satellite,context=context))
            if satellite in ('assist_satellite.bedroom','assist_satellite.kitchen'):
                call.assert_awaited_once_with('media_player','media_stop',
                    {'entity_id':'media_player.'+satellite.split('.')[1]},blocking=True,context=context)
            else:
                call.assert_not_awaited()
        hass.data['jarvis_local']['settings']['satellite_media_players']['assist_satellite.bedroom']='all'
        await stop.stop_player(hass,types.SimpleNamespace(satellite_id='assist_satellite.bedroom',context=context))
        call.assert_not_awaited()

    @immediate
    async def test_agent_stop_is_silent_while_busy_and_clears_only_own_dialogue(self):
        # Compile the actual handler, substituting only its external dependencies.
        tree=ast.parse((ROOT/'agent.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_handle')
        class Response:
            def __init__(self,**kwargs):pass
            def async_set_speech(self,text,**kwargs):self.speech=text
        ns=dict(perf_counter=perf_counter,monotonic=monotonic,
            intent=types.SimpleNamespace(IntentResponse=Response),
            conversation=types.SimpleNamespace(ConversationResult=lambda **kw:types.SimpleNamespace(**kw)),
            bridge_profile=lambda *args:None,is_spoken_stop=stop.is_spoken_stop,
            stop_player=stop.stop_player)
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual handler>','exec'),ns)
        context=types.SimpleNamespace(user_id='user')
        satellite='assist_satellite.bedroom'
        key=('user','one',satellite,None)
        other=('user','other','assist_satellite.kitchen',None)
        for phrase in ('Stop','Be quiet','Shut up'):
            for fail in (False,True):
                call=AsyncMock(side_effect=errors.HomeAssistantError() if fail else None)
                hass=types.SimpleNamespace(data={'jarvis_local':{'settings':{
                    'satellite_media_players':{satellite:'media_player.bedroom'}}}},
                    services=types.SimpleNamespace(async_call=call))
                agent=types.SimpleNamespace(hass=hass,_lock=asyncio.Lock(),
                    _recent_lights={k:{'at':monotonic()} for k in (key,other)},
                    _pending_clarifications={k:{'at':monotonic()} for k in (key,other)})
                await agent._lock.acquire()
                user=types.SimpleNamespace(language='en',conversation_id='one',context=context,
                    satellite_id=satellite,device_id=None,text=phrase)
                result=await ns['async_handle'](agent,user)
                self.assertEqual(result.response.speech,'')
                self.assertFalse(result.continue_conversation)
                self.assertEqual(set(agent._pending_clarifications),{other})
                self.assertEqual(set(agent._recent_lights),{other})
                self.assertTrue(agent._lock.locked())
                call.assert_awaited_once_with('media_player','media_stop',
                    {'entity_id':'media_player.bedroom'},blocking=True,context=context)

if __name__=='__main__':unittest.main()
