"""Read-only saved mapping checks and their administrator endpoint."""
import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'jarvis_local'
spec = importlib.util.spec_from_file_location('satellite_health_under_test', ROOT / 'satellite_health.py')
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class MappingHealth(unittest.TestCase):
    def setUp(self):
        self.entities = {
            'assist_satellite.bedroom': types.SimpleNamespace(state='idle'),
            'media_player.bedroom': types.SimpleNamespace(state='playing')}
        self.settings = {'satellite_media_players': {
            'assist_satellite.bedroom': 'media_player.bedroom'}}
        self.hass = types.SimpleNamespace(
            data={'jarvis_local': {'settings': self.settings}},
            states=types.SimpleNamespace(get=self.entities.get))
        # Any mutation or service call would fail: these interfaces are absent.

    def test_available_entities_are_checked_without_changing_configuration(self):
        original = deepcopy(self.hass.data)
        result = health.check_mappings(self.hass)
        self.assertIsNone(result['error'])
        self.assertEqual(result['mappings'], [{
            'satellite_id': 'assist_satellite.bedroom',
            'media_player_id': 'media_player.bedroom',
            'satellite_status': 'available', 'player_status': 'available',
            'entities_available': True, 'shared_player': False}])
        self.assertEqual(self.hass.data, original)
        self.assertEqual(self.entities['media_player.bedroom'].state, 'playing')

    def test_missing_unavailable_unknown_and_invalid_are_distinct(self):
        for entity in ('assist_satellite.bedroom', 'media_player.bedroom'):
            field = 'satellite_status' if entity.startswith('assist_satellite.') else 'player_status'
            for state in ('unavailable', 'unknown', None):
                with self.subTest(entity=entity, state=state):
                    original = self.entities[entity]
                    if state is None:
                        del self.entities[entity]
                    else:
                        self.entities[entity] = types.SimpleNamespace(state=state)
                    row = health.check_mappings(self.hass)['mappings'][0]
                    self.assertEqual(row[field], state or 'missing')
                    self.assertFalse(row['entities_available'])
                    self.entities[entity] = original
        for invalid in ('all', ['media_player.bedroom'], None):
            self.settings['satellite_media_players']['assist_satellite.bedroom'] = invalid
            row = health.check_mappings(self.hass)['mappings'][0]
            self.assertEqual(row['player_status'], 'invalid')
            self.assertFalse(row['entities_available'])

    def test_shared_player_warns_without_guessing_or_rewriting(self):
        self.settings['satellite_media_players']['assist_satellite.kitchen'] = 'media_player.bedroom'
        original = deepcopy(self.settings)
        rows = health.check_mappings(self.hass)['mappings']
        self.assertTrue(all(row['shared_player'] for row in rows))
        self.assertEqual(rows[1]['satellite_status'], 'missing')
        self.assertEqual(self.settings, original)

    def test_empty_and_corrupt_settings(self):
        self.settings.clear()
        self.assertEqual(health.check_mappings(self.hass), {'mappings': [], 'error': None})
        for invalid in ([], None, {str(i): 'media_player.bedroom' for i in range(51)}):
            self.settings['satellite_media_players'] = invalid
            result = health.check_mappings(self.hass)
            self.assertEqual(result['mappings'], [])
            self.assertIn('invalid', result['error'])

    def test_endpoint_returns_check_results_and_requires_admin(self):
        tree = ast.parse((ROOT / 'websocket.py').read_text(encoding='utf-8'))
        endpoint = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'check_satellite_mappings')
        # Retain the actual decorator wiring while substituting HA's authorization boundary.
        def require_admin(fn):
            def guarded(hass, connection, msg):
                if not connection.user.is_admin:
                    connection.send_error(msg['id'], 'unauthorized', 'Administrator required')
                    return
                return fn(hass, connection, msg)
            return guarded
        namespace = {
            'websocket_api': types.SimpleNamespace(
                require_admin=require_admin, websocket_command=lambda schema: lambda fn: fn),
            'vol': types.SimpleNamespace(Required=lambda name: name),
            'callback': lambda fn: fn, 'check_mappings': health.check_mappings}
        exec(compile(ast.Module(body=[endpoint], type_ignores=[]), '<actual health endpoint>', 'exec'), namespace)
        replies, errors = [], []
        connection = types.SimpleNamespace(
            user=types.SimpleNamespace(is_admin=False),
            send_result=lambda *args: replies.append(args), send_error=lambda *args: errors.append(args))
        namespace['check_satellite_mappings'](self.hass, connection, {'id': 1})
        self.assertEqual(replies, [])
        self.assertEqual(errors[0][1], 'unauthorized')
        connection.user.is_admin = True
        namespace['check_satellite_mappings'](self.hass, connection, {'id': 2})
        self.assertEqual(replies, [(2, health.check_mappings(self.hass))])


if __name__ == '__main__':
    unittest.main()
