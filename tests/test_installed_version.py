"""Installed metadata flows through setup, reload, API and panel URL."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'jarvis_local'
spec = importlib.util.spec_from_file_location('installed_version_under_test', ROOT / 'version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


def complete(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError('Fixture unexpectedly suspended')


def function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class InstalledVersion(unittest.TestCase):
    def test_installed_manifest_reader(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(version.read_version(), manifest['version'])

    def test_reload_refreshes_reported_version_and_frontend_url(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest_path = folder / 'manifest.json'
            registration = AsyncMock()
            timers_module = types.ModuleType('version_test_pkg.timers')
            class Timers:
                def __init__(self, hass): pass
                async def start(self): pass
            timers_module.Timers = Timers
            settings_module = types.ModuleType('version_test_pkg.settings')
            settings_module.load = AsyncMock(return_value={})
            media_config = types.ModuleType('version_test_pkg.media_search_config')
            media_config.load = AsyncMock(return_value={'region':'GB','subscriptions':[],'tmdb_token':''})
            storage_module = types.ModuleType('homeassistant.helpers.storage')
            class Store:
                def __init__(self, *args): pass
                async def async_load(self): return {}
            storage_module.Store = Store
            package = types.ModuleType('version_test_pkg')
            package.__path__ = []
            modules = {'version_test_pkg': package,
                       'version_test_pkg.media_search_config': media_config,
                       'version_test_pkg.timers': timers_module,
                       'version_test_pkg.settings': settings_module,
                       'homeassistant.helpers.storage': storage_module}
            data = {'ws_registered': True, 'static_registered': True,
                    'agent': types.SimpleNamespace(entity_id='conversation.jarvis')}
            async def executor(call, *args):
                return call(*args)
            hass = types.SimpleNamespace(
                data={'jarvis_local': data},
                async_add_executor_job=executor,
                config=types.SimpleNamespace(path=lambda name: str(folder / name)),
                config_entries=types.SimpleNamespace(async_forward_entry_setups=AsyncMock()))
            setup = function(ROOT / '__init__.py', 'async_setup_entry', {
                '__package__': 'version_test_pkg', 'DOMAIN': 'jarvis_local',
                'Path': Path, 'quote': quote, 'read_version': version.read_version,
                'panel_custom': types.SimpleNamespace(async_register_panel=registration)})
            info = function(ROOT / 'websocket.py', 'info', {
                'ar': types.SimpleNamespace(async_get=lambda hass: types.SimpleNamespace(async_list_areas=lambda: [])),
                'public_profiles': lambda value: {},
                'public_media_search': lambda hass: {'region':'GB','subscriptions':[],'catalogue_configured':False}})
            replies = []
            connection = types.SimpleNamespace(send_result=lambda request_id, result: replies.append(result))
            with patch.dict(sys.modules, modules), patch.object(version, '__file__', str(folder / 'version.py')):
                for installed in ('1.2.3', '1.2.4'):
                    manifest_path.write_text(json.dumps({'version': installed}), encoding='utf-8')
                    self.assertTrue(complete(setup(hass, object())))
                    self.assertEqual(data['version'], installed)
                    self.assertEqual(registration.call_args.kwargs['module_url'],
                                     '/jarvis_local/panel.js?v=' + installed)
                    info(hass, connection, {'id': 1})
                    self.assertEqual(replies[-1]['version'], installed)
            self.assertEqual(registration.await_count, 2)

    def test_invalid_metadata_is_not_reported_as_a_valid_version(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(version, '__file__', str(folder / 'version.py')):
                for value in (None, '', '   ', 123, []):
                    (folder / 'manifest.json').write_text(json.dumps({'version': value}), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        version.read_version()


if __name__ == '__main__':
    unittest.main()
