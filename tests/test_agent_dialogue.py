"""Dialogue integration tests with mocked Home Assistant services."""
import sys,types,unittest
import test_commands as fixtures
conv=types.ModuleType('homeassistant.components.conversation')
class ConversationEntity:pass
class Result:
    def __init__(self,response,conversation_id,continue_conversation=False):self.response=response;self.conversation_id=conversation_id;self.continue_conversation=continue_conversation
conv.ConversationEntity=ConversationEntity
conv.ConversationEntityFeature=types.SimpleNamespace(CONTROL=1)
conv.ConversationResult=Result
sys.modules[conv.__name__]=conv
intent=types.ModuleType('homeassistant.helpers.intent')
class Response:
    def __init__(self,language):self.speech=''
    def async_set_speech(self,speech,extra_data=None):self.speech=speech;self.extra_data=extra_data
intent.IntentResponse=Response;sys.modules[intent.__name__]=intent
exceptions=types.ModuleType('homeassistant.exceptions');exceptions.HomeAssistantError=type('HomeAssistantError',(Exception,),{});sys.modules[exceptions.__name__]=exceptions
storage=types.ModuleType('homeassistant.helpers.storage');storage.Store=object;sys.modules[storage.__name__]=storage
satellite=types.ModuleType('homeassistant.components.assist_satellite');satellite.AssistSatelliteEntityFeature=types.SimpleNamespace(ANNOUNCE=1);sys.modules[satellite.__name__]=satellite
from jarvis_test import agent as module
async def verify(*args):return []
async def confirmation(hass,context,fallback,action='general'):return fallback
module.verify=verify;module.confirmation=confirmation
class Services:
    def __init__(self):self.calls=[]
    async def async_call(self,*args,**kwargs):self.calls.append((args,kwargs));return {}
class UserInput:
    def __init__(self,text,cid='one',device=None):self.text=text;self.conversation_id=cid;self.context=types.SimpleNamespace(user_id='user');self.device_id=device;self.satellite_id=None;self.language='en'
class Dialogue(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hass=fixtures.Hass();self.hass.data={};self.hass.services=Services();self.agent=module.JarvisAgent(self.hass)
    async def test_clarification_then_action_and_followup(self):
        first=await self.agent.async_handle(UserInput('lamp on'))
        self.assertTrue(first.continue_conversation);self.assertEqual(self.hass.services.calls,[])
        reply=await self.agent.async_handle(UserInput('the bedroom one'))
        self.assertFalse(reply.continue_conversation);self.assertEqual(self.hass.services.calls[0][0][2]['entity_id'],['light.bedroom'])
        await self.agent.async_handle(UserInput('turn it off'))
        self.assertEqual(self.hass.services.calls[1][0][1],'turn_off')
    async def test_frequency_metadata_requires_success(self):
        rejected=await self.agent.async_handle(UserInput('offers life on'))
        self.assertFalse(rejected.response.extra_data['jarvis_local']['trackable'])
        clarification=await self.agent.async_handle(UserInput('lamp on'))
        self.assertFalse(clarification.response.extra_data['jarvis_local']['trackable'])
        completed=await self.agent.async_handle(UserInput('bedroom'))
        self.assertTrue(completed.response.extra_data['jarvis_local']['trackable'])
        preview=await self.agent.async_handle(UserInput('preview turn bedroom light on'))
        self.assertFalse(preview.response.extra_data['jarvis_local']['trackable'])
    async def test_debug_history_disabled_by_default(self):
        await self.agent.async_handle(UserInput('lamp on'))
        self.assertFalse(self.hass.data['jarvis_local'].get('diagnostics'))
        self.hass.data['jarvis_local']['debug_enabled']=True
        await self.agent.async_handle(UserInput('cancel'))
        self.assertEqual(len(self.hass.data['jarvis_local']['diagnostics']),1)
    async def test_social_reply_unknown_and_matched(self):
        neutral=await self.agent.async_handle(UserInput('thank you'))
        self.assertNotIn('Jaco',neutral.response.speech)
        original=module.bridge_profile
        try:
            module.bridge_profile=lambda text,profiles:'Jaco'
            named=await self.agent.async_handle(UserInput('hello'))
            self.assertIn('Jaco',named.response.speech)
            self.assertEqual(self.hass.services.calls,[])
        finally:module.bridge_profile=original
    async def test_compound_followup_applies_to_all_targets(self):
        await self.agent.async_handle(UserInput('turn office and bedroom lamp on'))
        self.assertEqual(len(self.hass.services.calls),2)
        await self.agent.async_handle(UserInput('turn them off'))
        self.assertEqual(self.hass.services.calls[-1][0][1],'turn_off')
        self.assertEqual(set(self.hass.services.calls[-1][0][2]['entity_id']),{'light.office','light.bedroom'})
    async def test_switch_backed_compound_followup(self):
        self.hass.data={'jarvis_local':{'settings':{'switch_lights':{'queen lamp':'switch.queen'}}}}
        self.hass.states.values['switch.queen']=fixtures.State('switch.queen','Queen Lamp')
        await self.agent.async_handle(UserInput('turn office and queen lamp off'))
        self.assertEqual(len(self.hass.services.calls),2)
        await self.agent.async_handle(UserInput('turn them back on'))
        self.assertEqual(len(self.hass.services.calls),4)
        self.assertEqual(self.hass.services.calls[-1][0][:2],('switch','turn_on'))
        self.assertEqual(self.hass.services.calls[-1][0][2]['entity_id'],['switch.queen'])
    async def test_combined_response_once_and_again_followup(self):
        self.hass.data={'jarvis_local':{'settings':{'switch_lights':{'queen lamp':'switch.queen'}}}}
        self.hass.states.values['switch.queen']=fixtures.State('switch.queen','Queen Lamp')
        first=await self.agent.async_handle(UserInput('office and queen lamp off'))
        self.assertEqual(first.response.speech,'Turning off the lights.')
        await self.agent.async_handle(UserInput('turn them back on'))
        final=await self.agent.async_handle(UserInput('turn them off again'))
        self.assertEqual(len(self.hass.services.calls),6)
        self.assertEqual(final.response.speech,'Turning off the lights.')
    async def test_missing_switch_followup_has_no_partial_action(self):
        self.hass.data={'jarvis_local':{'settings':{'switch_lights':{'queen lamp':'switch.queen'}}}}
        self.hass.states.values['switch.queen']=fixtures.State('switch.queen','Queen Lamp')
        await self.agent.async_handle(UserInput('turn office and queen lamp off'))
        self.hass.hidden.add('switch.queen')
        await self.agent.async_handle(UserInput('turn them back on'))
        self.assertEqual(len(self.hass.services.calls),2)
    async def test_failed_command_does_not_leave_stale_followup(self):
        await self.agent.async_handle(UserInput('office on'))
        await self.agent.async_handle(UserInput('turn office and missing light off'))
        response=await self.agent.async_handle(UserInput('turn them back on'))
        self.assertIn('Which lights',response.response.speech)
        self.assertEqual(len(self.hass.services.calls),1)
    async def test_bad_compound_executes_nothing(self):
        await self.agent.async_handle(UserInput('turn office and missing light on'))
        self.assertEqual(self.hass.services.calls,[])
    async def test_in_sentence_correction_runs_only_final_command(self):
        self.hass.states.values['script.jarvis_local_movie']=fixtures.State(
            'script.jarvis_local_movie','Movie Mode','off')
        result=await self.agent.async_handle(
            UserInput('Dinner on, no I mean movie time'))
        self.assertEqual(len(self.hass.services.calls),1)
        self.assertEqual(self.hass.services.calls[0][0][:2],('script','jarvis_local_movie'))
        self.assertIn('Make up your',result.response.speech)

    async def test_incomplete_correction_runs_nothing(self):
        result=await self.agent.async_handle(UserInput('Lights on, scratch that'))
        self.assertEqual(self.hass.services.calls,[])
        self.assertIn('Nothing was run',result.response.speech)
    async def test_other_conversation_cannot_answer(self):
        await self.agent.async_handle(UserInput('lamp on'))
        await self.agent.async_handle(UserInput('bedroom','other'))
        self.assertEqual(self.hass.services.calls,[])
    async def test_preview_and_cancel_do_not_execute(self):
        result=await self.agent.async_handle(UserInput('preview lamp on'))
        self.assertTrue(result.continue_conversation)
        reply=await self.agent.async_handle(UserInput('bedroom'))
        self.assertIn('Preview only',reply.response.speech);self.assertEqual(self.hass.services.calls,[])
        await self.agent.async_handle(UserInput('lamp on'))
        reply=await self.agent.async_handle(UserInput('cancel'))
        self.assertIn('Cancelled',reply.response.speech);self.assertEqual(self.hass.services.calls,[])
    async def test_media_preview_and_execution(self):
        player=fixtures.State('media_player.bedroom','Bedroom Speaker','playing')
        player.attributes={'supported_features':15}
        self.hass.states.values[player.entity_id]=player
        self.hass.entities.entries[player.entity_id]=types.SimpleNamespace(area_id='bedroom',device_id=None,disabled_by=None,hidden_by=None,aliases=set())
        preview=await self.agent.async_handle(UserInput('preview pause music in bedroom'))
        self.assertIn('Preview only',preview.response.speech);self.assertEqual(self.hass.services.calls,[])
        await self.agent.async_handle(UserInput('pause music in bedroom'))
        self.assertEqual(self.hass.services.calls[0][0],('media_player','media_pause',{'entity_id':'media_player.bedroom'}))
    async def test_expired_and_removed_entities_do_not_execute(self):
        await self.agent.async_handle(UserInput('lamp on'))
        for v in self.agent._pending_clarifications.values():v['at']-=121
        await self.agent.async_handle(UserInput('bedroom'))
        self.assertEqual(self.hass.services.calls,[])
        await self.agent.async_handle(UserInput('lamp on'))
        self.hass.hidden.add('light.bedroom')
        await self.agent.async_handle(UserInput('bedroom'))
        self.assertEqual(self.hass.services.calls,[])
if __name__=='__main__':unittest.main()
