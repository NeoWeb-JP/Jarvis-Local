"""Satellite mapping persistence and validation without a live HA instance."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'jarvis_local'
storage = types.ModuleType('homeassistant.helpers.storage')
storage.Store = object
spec = importlib.util.spec_from_file_location('mapping_settings_under_test', ROOT / 'settings.py')
settings = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'homeassistant.helpers.storage': storage}):
    spec.loader.exec_module(settings)

BED = 'assist_satellite.bedroom'
PLAYER = 'media_player.bedroom'


def complete(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError('Fixture unexpectedly suspended')


class Settings(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name) / 'settings.json'
        class Store:
            def __init__(self, *args): pass
            async def async_save(self, data):
                path.write_text(json.dumps(data), encoding='utf-8')
            async def async_load(self):
                return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        self.patch = patch.object(settings, 'Store', Store)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.path = path
        self.entities = {BED, PLAYER, 'assist_satellite.kitchen', 'media_player.kitchen'}
        self.hass = types.SimpleNamespace(
            data={'jarvis_local': {'settings': {}}},
            states=types.SimpleNamespace(get=lambda entity: object() if entity in self.entities else None))

    def save(self, data):
        complete(settings.save(self.hass, data))

    def test_save_reload_edit_and_remove(self):
        self.save({'satellite_media_players': {BED: PLAYER}})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], {BED: PLAYER})
        self.save({'satellite_media_players': {BED: 'media_player.kitchen'}})
        self.assertEqual(self.hass.data['jarvis_local']['settings']['satellite_media_players'][BED], 'media_player.kitchen')
        self.save({'satellite_media_players': {}})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], {})

    def test_older_client_preserves_mapping(self):
        self.save({'satellite_media_players': {BED: PLAYER}})
        self.save({'switch_lights': {}})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], {BED: PLAYER})

    def test_unchanged_missing_mapping_can_be_kept_or_removed(self):
        self.save({'satellite_media_players': {BED: PLAYER}})
        self.entities.clear()
        self.save({'satellite_media_players': {BED: PLAYER}})
        self.save({})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], {BED: PLAYER})
        self.save({'satellite_media_players': {}})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], {})

    def test_invalid_mapping_is_atomic(self):
        self.save({'satellite_media_players': {BED: PLAYER}})
        before = self.path.read_text()
        invalid = [
            None, [], {BED: ['media_player.bedroom']}, {BED: 'all'},
            {'media_player.bedroom': PLAYER}, {BED: PLAYER + ',media_player.kitchen'},
            {BED: 'media_player.missing'}, {'assist_satellite.missing': PLAYER},
            {f'assist_satellite.room_{i}': PLAYER for i in range(51)},
        ]
        for mappings in invalid:
            with self.subTest(mappings=mappings):
                with self.assertRaises(ValueError):
                    self.save({'satellite_media_players': mappings})
                self.assertEqual(self.path.read_text(), before)
                self.assertEqual(self.hass.data['jarvis_local']['settings']['satellite_media_players'], {BED: PLAYER})

    def test_two_satellites_and_shared_player_are_explicit(self):
        # Shared physical speakers are permitted only through explicit selections.
        mappings = {BED: PLAYER, 'assist_satellite.kitchen': PLAYER}
        self.save({'satellite_media_players': mappings})
        self.assertEqual(complete(settings.load(self.hass))['satellite_media_players'], mappings)


if __name__ == '__main__':
    unittest.main()
