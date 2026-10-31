"""Diagnostics exercise the actual stop handler and debug-toggle implementation."""
import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, perf_counter
import types
import unittest
from unittest.mock import AsyncMock
from test_satellite_stop import stop, immediate, errors

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'jarvis_local'
SATELLITE = 'assist_satellite.bedroom'
PLAYER = 'media_player.bedroom'


def handler():
    tree = ast.parse((ROOT / 'agent.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'async_handle')
    class Response:
        def __init__(self, **kwargs): pass
        def async_set_speech(self, speech, **kwargs):
            self.speech = speech
            self.extra_data = kwargs.get('extra_data')
    namespace = dict(
        perf_counter=perf_counter, monotonic=monotonic, datetime=datetime, timezone=timezone,
        intent=types.SimpleNamespace(IntentResponse=Response),
        conversation=types.SimpleNamespace(ConversationResult=lambda **kwargs: types.SimpleNamespace(**kwargs)),
        bridge_profile=lambda *args: None,
        unwrap=lambda *args: ('Stop', None),
        is_spoken_stop=stop.is_spoken_stop, stop_player=stop.stop_player,
    )
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual stop handler>', 'exec'), namespace)
    return namespace['async_handle']


class StopDiagnostics(unittest.TestCase):
    def setUp(self):
        self.process = handler()
        self.context = types.SimpleNamespace(user_id='user')
        self.call = AsyncMock()
        self.data = {'settings': {'satellite_media_players': {SATELLITE: PLAYER}}, 'debug_enabled': True}
        self.hass = types.SimpleNamespace(
            data={'jarvis_local': self.data}, services=types.SimpleNamespace(async_call=self.call))
        self.agent = types.SimpleNamespace(
            hass=self.hass, _lock=asyncio.Lock(), _recent_lights={},
            _pending_clarifications={}, _voice_markers={})

    async def request(self, satellite=SATELLITE, text='Stop'):
        user = types.SimpleNamespace(
            text=text, language='en', conversation_id='test', context=self.context,
            satellite_id=satellite, device_id=None)
        result = await self.process(self.agent, user)
        self.assertEqual(result.response.speech, '')
        self.assertFalse(result.continue_conversation)
        self.assertFalse(result.response.extra_data['jarvis_local']['trackable'])
        return (self.data.get('diagnostics') or [None])[-1]

    @immediate
    async def test_success_reports_request_without_claiming_playback_verified(self):
        record = await self.request()
        self.assertEqual(record['satellite_id'], SATELLITE)
        self.assertEqual(record['stop'], {
            'outcome': 'completed', 'reason': 'request_sent',
            'media_player_id': PLAYER, 'service_called': True})
        self.assertEqual(record['response'], '')
        self.assertTrue(record['steps'][0]['unverified'])
        self.assertEqual(record['steps'][0]['data'], {'entity_id': PLAYER})
        self.assertGreaterEqual(record['elapsed_ms'], 0)
        self.call.assert_awaited_once_with('media_player', 'media_stop',
            {'entity_id': PLAYER}, blocking=True, context=self.context)

    @immediate
    async def test_skipped_routes_are_distinct_and_run_no_actions(self):
        cases = [
            (None, {SATELLITE: PLAYER}, 'missing_satellite'),
            ('assist_satellite.kitchen', {SATELLITE: PLAYER}, 'unmapped_satellite'),
            (SATELLITE, [], 'invalid_mapping'),
            (SATELLITE, {SATELLITE: 'all'}, 'invalid_mapping'),
            (SATELLITE, {SATELLITE: ['media_player.bedroom']}, 'invalid_mapping'),
        ]
        for satellite, mappings, reason in cases:
            self.data['settings']['satellite_media_players'] = mappings
            record = await self.request(satellite)
            self.assertEqual(record['outcome'], 'skipped')
            self.assertEqual(record['stop']['reason'], reason)
            self.assertIsNone(record['stop']['media_player_id'])
            self.assertFalse(record['stop']['service_called'])
            self.assertEqual(record['steps'], [])
        self.call.assert_not_awaited()

    @immediate
    async def test_failures_and_timeouts_stay_silent_and_do_not_store_exception_text(self):
        for error, reason in [
            (errors.HomeAssistantError('private backend details'), 'service_error'),
            (TimeoutError('private timeout details'), 'service_timeout'),
        ]:
            self.call.side_effect = error
            with self.assertLogs(stop._LOGGER, level='WARNING'):
                record = await self.request()
            self.assertEqual(record['outcome'], 'failed')
            self.assertEqual(record['stop']['reason'], reason)
            self.assertTrue(record['stop']['service_called'])
            self.assertNotIn('private', str(record))

    @immediate
    async def test_debug_is_opt_in_and_history_is_bounded(self):
        self.data.pop('debug_enabled')
        await self.request()
        self.assertNotIn('diagnostics', self.data)
        self.data['debug_enabled'] = True
        for _ in range(25):
            await self.request()
        self.assertEqual(len(self.data['diagnostics']), 20)

    @immediate
    async def test_debug_disabled_during_request_does_not_repopulate_history(self):
        def disable(*args, **kwargs):
            self.data['debug_enabled'] = False
            self.data['diagnostics'] = []
        self.call.side_effect = disable
        await self.request()
        self.assertEqual(self.data['diagnostics'], [])

    @immediate
    async def test_voice_bridge_envelope_is_not_recorded(self):
        record = await self.request(text='JVS1.private-signed-envelope')
        self.assertEqual(record['received_text'], 'Stop')
        self.assertEqual(record['resolved_text'], 'Stop')
        self.assertNotIn('JVS1', str(record))

    @immediate
    async def test_task_cancellation_is_not_swallowed(self):
        self.call.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.request()
        self.assertNotIn('diagnostics', self.data)

    @immediate
    async def test_existing_debug_toggle_clears_stop_records(self):
        await self.request()
        tree = ast.parse((ROOT / 'websocket.py').read_text(encoding='utf-8'))
        method = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'set_debug')
        method.decorator_list = []
        saves = []
        class Store:
            def __init__(self, *args): pass
            async def async_save(self, data): saves.append(data)
        namespace = {'Store': Store}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual debug toggle>', 'exec'), namespace)
        replies = []
        connection = types.SimpleNamespace(send_result=lambda *args: replies.append(args))
        await namespace['set_debug'](self.hass, connection, {'id': 1, 'enabled': False})
        self.assertEqual(self.data['diagnostics'], [])
        self.assertFalse(self.data['debug_enabled'])
        self.assertEqual(saves, [{'enabled': False}])
        await self.request()
        self.assertEqual(self.data['diagnostics'], [])


if __name__ == '__main__':
    unittest.main()
