"""Regression checks against lightweight Home Assistant fixtures."""
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'custom_components' / 'jarvis_local'
pkg=types.ModuleType('jarvis_test');pkg.__path__=[str(root)];sys.modules['jarvis_test']=pkg
for name in ['homeassistant','homeassistant.helpers','homeassistant.components','homeassistant.components.homeassistant']:
    module=types.ModuleType(name);module.__path__=[];sys.modules[name]=module
for name, attr in [('area_registry','areas'),('device_registry','devices'),('entity_registry','entities')]:
    module=types.ModuleType('homeassistant.helpers.'+name)
    module.async_get=lambda hass, attr=attr:getattr(hass,attr)
    sys.modules[module.__name__]=module
exposed=types.ModuleType('homeassistant.components.homeassistant.exposed_entities')
exposed.async_should_expose=lambda hass, domain, entity: entity not in hass.hidden
sys.modules[exposed.__name__]=exposed
media=types.ModuleType('homeassistant.components.media_player')
media.MediaPlayerEntityFeature=types.SimpleNamespace(PAUSE=1,PLAY=2,NEXT_TRACK=4,VOLUME_SET=8)
sys.modules[media.__name__]=media
from jarvis_test.discovery import lighting
from jarvis_test.room_context import apply_room
from jarvis_test.followup import followup
from jarvis_test.clarification import request, resolve
from jarvis_test.media import media_plan

class State:
    def __init__(self, entity_id, name, state='on', modes=('brightness',)):
        self.entity_id=entity_id;self.name=name;self.state=state
        self.attributes={'supported_color_modes':modes,'brightness':128}
class Registry:
    def __init__(self, entries):self.entries=entries
    def async_get(self, key):return self.entries.get(key)
    def async_list_areas(self):return list(self.entries.values())
    def async_get_area(self, key):return self.entries.get(key)
class States:
    def __init__(self, states):self.values={x.entity_id:x for x in states}
    def get(self, key):return self.values.get(key)
    def async_all(self, domain):return [s for s in self.values.values() if s.entity_id.startswith(domain+'.')]
class Hass:
    def __init__(self):
        self.hidden=set()
        self.states=States([State('light.office','Office'),State('light.kitchen','Kitchen Lamp'),State('light.bedroom','Bedroom Lamp'),State('light.hidden','Hidden')])
        self.areas=Registry({key:types.SimpleNamespace(id=key,name=name,aliases=set()) for key,name in [('office','Office'),('kitchen','Kitchen'),('bedroom','Bedroom')]})
        self.entities=Registry({key:types.SimpleNamespace(area_id=room,device_id=None,disabled_by=None,hidden_by=None,aliases=aliases) for key,room,aliases in [('light.office','office',set()),('light.kitchen','kitchen',{'lamp'}),('light.bedroom','bedroom',{'lamp'}),('light.hidden','office',set())]})
        self.devices=Registry({});self.hidden.add('light.hidden')

class Commands(unittest.TestCase):
    def setUp(self):self.hass=Hass()
    def test_short_command_and_punctuation(self):
        step=lighting(self.hass,'Office off.')
        self.assertEqual(step['data']['entity_id'],['light.office']);self.assertEqual(step['name'],'turn_off')
    def test_exposure_excludes_hidden(self):
        step=lighting(self.hass,'Office on')
        self.assertNotIn('light.hidden',step['data']['entity_id'])
    def test_ambiguous_name_lists_options_and_does_not_return_action(self):
        with self.assertRaises(ValueError) as error:lighting(self.hass,'lamp on')
        self.assertIn('Kitchen Lamp',str(error.exception));self.assertIn('Bedroom Lamp',str(error.exception))
    def test_room_context_uses_local_lamp(self):
        text=apply_room('lamp on',self.hass.areas.entries['bedroom'],self.hass)
        self.assertEqual(lighting(self.hass,text)['data']['entity_id'],['light.bedroom'])
    def test_percentage(self):
        step=lighting(self.hass,'Set office to 30%.')
        self.assertEqual(step['calls'][0]['data']['brightness_pct'],30)
    def test_followup_request(self):
        self.assertIsNotNone(followup('set them to 30 percent'))
    def add_spotlight(self, entity_id, name, area):
        self.hass.states.values[entity_id]=State(entity_id,name)
        self.hass.entities.entries[entity_id]=types.SimpleNamespace(area_id=area,device_id=None,disabled_by=None,hidden_by=None,aliases=set())
    def test_spotlights_apply_to_selected_area_only(self):
        self.add_spotlight('light.bed_spotlight_1','Bed Spot Light 1','bedroom')
        self.add_spotlight('light.bed_spotlight_2','Bed Spotlight 2','bedroom')
        self.add_spotlight('light.kitchen_spotlight','Kitchen Spotlights','kitchen')
        phrase=apply_room('preview Spotlights on',self.hass.areas.entries['bedroom'],self.hass)
        self.assertTrue(phrase.startswith('preview '))
        step=lighting(self.hass,phrase.removeprefix('preview '))
        self.assertEqual(step['data']['entity_id'],['light.bed_spotlight_1','light.bed_spotlight_2'])
    def test_spotlights_without_matches_do_not_control_other_lights(self):
        with self.assertRaisesRegex(ValueError,'could not find'):
            apply_room('spotlights on',self.hass.areas.entries['bedroom'],self.hass)
    def test_singular_multiple_spotlights_is_ambiguous(self):
        self.add_spotlight('light.spotlight_1','Spotlight 1','bedroom')
        self.add_spotlight('light.spotlight_2','Spotlight 2','bedroom')
        with self.assertRaisesRegex(ValueError,'Which spotlight'):
            apply_room('spotlight on',self.hass.areas.entries['bedroom'],self.hass)
    def test_spotlight_brightness_is_area_scoped(self):
        self.add_spotlight('light.spotlight_1','Spot Light 1','bedroom')
        phrase=apply_room('set spotlights to 30%',self.hass.areas.entries['bedroom'],self.hass)
        step=lighting(self.hass,phrase)
        self.assertEqual(step['calls'][0]['data'],{'entity_id':['light.spotlight_1'],'brightness_pct':30})
    def test_clarification_unique_room_answer_and_preview(self):
        pending=request(self.hass,'preview turn the lamp on',None)
        self.assertTrue(pending['preview'])
        self.assertEqual(resolve(pending,'the bedroom one'),('resolved','light.bedroom'))
        self.assertEqual(resolve(pending,'the kitchen one'),('resolved','light.kitchen'))
        self.assertEqual(resolve(pending,'the lamp'),('unclear',None))
        self.assertEqual(resolve(pending,'cancel'),('cancel',None))
    def test_clarification_does_not_intercept_compound(self):
        self.assertIsNone(request(self.hass,'turn lamp and office on',None))
    def test_clarification_room_scope(self):
        self.assertIsNone(request(self.hass,'lamp on',self.hass.areas.entries['bedroom']))
    def test_revalidation_excluded_entity_is_not_selected(self):
        pending=request(self.hass,'lamp on',None)
        entity=resolve(pending,'bedroom')[1]
        self.hass.hidden.add(entity)
        self.assertIsNone(lighting(self.hass,'turn on '+entity))
    def test_followup_prior_lights_revalidates_exposure(self):
        self.hass.hidden.add('light.bedroom')
        with self.assertRaisesRegex(ValueError,'no longer available'):
            lighting(self.hass,'turn off __previous_lights__',['light.bedroom'])
    def add_player(self, entity_id, name, area, features=15, state='playing'):
        player=State(entity_id,name,state);player.attributes={'supported_features':features}
        self.hass.states.values[entity_id]=player
        self.hass.entities.entries[entity_id]=types.SimpleNamespace(area_id=area,device_id=None,disabled_by=None,hidden_by=None,aliases=set())
    def test_media_controls_require_unique_player(self):
        self.add_player('media_player.kitchen','Kitchen Speaker','kitchen')
        self.add_player('media_player.bedroom','Bedroom Speaker','bedroom')
        step=media_plan(self.hass,'pause music in kitchen')
        self.assertEqual(step['data']['entity_id'],'media_player.kitchen')
        with self.assertRaisesRegex(ValueError,'Which media player'):media_plan(self.hass,'pause music')
        self.assertEqual(media_plan(self.hass,'next song',self.hass.areas.entries['bedroom'])['name'],'media_next_track')
    def test_media_volume_validation_and_exposure(self):
        self.add_player('media_player.kitchen','Kitchen Speaker','kitchen')
        step=media_plan(self.hass,'set volume on kitchen to 30%')
        self.assertEqual(step['data']['volume_level'],0.3)
        with self.assertRaises(ValueError):media_plan(self.hass,'set volume on kitchen to 101%')
        self.hass.hidden.add('media_player.kitchen')
        with self.assertRaises(ValueError):media_plan(self.hass,'pause music in kitchen')
    def test_media_does_not_control_unsupported_or_off(self):
        self.add_player('media_player.kitchen','Kitchen Speaker','kitchen',features=2)
        with self.assertRaisesRegex(ValueError,'does not report'):media_plan(self.hass,'pause music in kitchen')
        self.hass.states.values['media_player.kitchen'].state='off'
        with self.assertRaisesRegex(ValueError,'unavailable or off'):media_plan(self.hass,'resume music in kitchen')
    def test_unrecognised_target_does_not_run(self):
        self.assertIsNone(lighting(self.hass,'unknown room on'))
if __name__=='__main__':unittest.main()
