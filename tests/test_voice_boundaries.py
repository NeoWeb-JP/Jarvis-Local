"""Voice correction regressions without a running Home Assistant."""
import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class VoiceBoundaries(unittest.TestCase):
    def setUp(self):
        self.names = {'queen lamp': {'light.queen'}}
        package = '_voice_boundary_fixture'
        modules = {}
        for name in [package, package+'.discovery', package+'.named_switches',
                     package+'.planner', package+'.room_context',
                     'homeassistant', 'homeassistant.helpers']:
            modules[name] = ModuleType(name)
        discovery = modules[package+'.discovery']
        discovery.norm = lambda text: re.sub(r'\s+', ' ', text.lower().strip().rstrip('.?!'))
        discovery.lighting = lambda *args: None
        discovery.inventory = lambda hass: ({}, list(self.ids))
        discovery.text_aliases = lambda value: {value.lower()} if isinstance(value,str) else set(value or [])
        modules[package+'.named_switches'].named_switch = None
        registry = SimpleNamespace(async_get=lambda entity: SimpleNamespace(aliases=self.aliases.get(entity,[])))
        modules['homeassistant.helpers'].entity_registry = SimpleNamespace(async_get=lambda hass: registry)
        self.planned = []
        def plan(hass, text, area):
            self.planned.append(text)
            if text not in {'queen lamp off', 'queen lamp on', 'turn queen lamp off', 'please queen lamp off please'}:
                raise ValueError('unsupported')
            return ([{'kind':'light','name':'turn_off','data':{'entity_id':['light.queen']}}], False)
        modules[package+'.planner'].plan = plan
        modules[package+'.room_context'].apply_room = lambda text,area,hass: text
        self.ids = {'light.queen': 'Queen Lamp'}
        self.aliases = {}
        self.hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity: SimpleNamespace(name=self.ids[entity])))
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location(package+'.transcript', ROOT/'custom_components/jarvis_local/transcript.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.modules = modules

    def correct(self,text):
        with patch.dict(sys.modules,self.modules):
            return self.module.correct(self.hass,text)

    def test_queen_variations(self):
        for text, expected in [
            ('Queen Lampoff','queen lamp off'),
            ('Queen Lampon.','queen lamp on'),
            ('Queen, Lampoff.','queen lamp off'),
            ('Queen. Lamp off.','queen lamp off'),
            ('turn Queen Lampoff','turn queen lamp off'),
            ('please Queen Lampoff please','please queen lamp off please'),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.correct(text)[0],expected)

    def test_alias(self):
        self.ids = {'light.queen':'Bedside'}
        self.aliases = {'light.queen':['queen lamp']}
        self.assertEqual(self.correct('Queen Lampoff')[0],'queen lamp off')

    def test_ambiguous_alias_is_not_corrected(self):
        self.ids['light.other']='Queen Lamp'
        self.assertEqual(self.correct('Queen Lampoff'),('Queen Lampoff',[]))
        self.assertEqual(self.planned,[])

    def test_unknown_or_unexposed_name(self):
        self.ids = {}
        self.assertEqual(self.correct('Queen Lampoff'),('Queen Lampoff',[]))

    def test_conversational_inputs_do_not_become_actions(self):
        for text in ['no, Queen Lampoff', 'stop. Queen Lampoff',
                     'actually Queen Lampoff', 'Queen Lampoff and kitchen on',
                     'Queen Lampoff or on', "don't Queen Lampoff",
                     'Queen Lamppoff', 'Queen Lampoff tomorrow']:
            with self.subTest(text=text):
                self.assertEqual(self.correct(text),(text,[]))

    def test_punctuation_does_not_remove_semantic_words(self):
        for text in ['no, Queen Lamp off.', 'stop. Queen Lamp off.',
                     'actually, Queen Lamp off.']:
            with self.subTest(text=text):
                self.assertEqual(self.correct(text),(text,[]))
                self.assertTrue(any(word in self.planned[-1] for word in ['no','stop','actually']))

if __name__ == '__main__':
    unittest.main()
