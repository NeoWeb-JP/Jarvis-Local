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
from jarvis_test.discovery import lighting
from jarvis_test.room_context import apply_room
from jarvis_test.followup import followup

class State:
    def __init__(self, entity_id, name, state='on', modes=('brightness',)):
        self.entity_id=entity_id;self.name=name;self.state=state
        self.attributes={'supported_color_modes':modes,'brightness':128}
class Registry:
    def __init__(self, entries):self.entries=entries
    def async_get(self, key):return self.entries.get(key)
    def async_list_areas(self):return list(self.entries.values())
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
    def test_unrecognised_target_does_not_run(self):
        self.assertIsNone(lighting(self.hass,'unknown room on'))
if __name__=='__main__':unittest.main()
