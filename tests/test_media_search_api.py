"""Authenticated API wiring and HTTP request contract for search-only media."""
import ast
import json
import sys
from pathlib import Path
import types
import unittest
from unittest.mock import AsyncMock, patch
from test_media_search import adapters, config, media, complete

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "jarvis_local"


def load_endpoint(name, namespace):
    tree = ast.parse((ROOT / "websocket.py").read_text(encoding="utf-8"))
    fn = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    # These tests execute handler behavior; administrator wiring is tested below.
    fn.decorator_list = []
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<actual websocket handler>", "exec"), namespace)
    return namespace[name]


class MediaAPI(unittest.TestCase):
    def setUp(self):
        self.hass = types.SimpleNamespace(data={"jarvis_local": {}})
        self.results, self.errors = [], []
        self.connection = types.SimpleNamespace(
            send_result=lambda *args: self.results.append(args),
            send_error=lambda *args: self.errors.append(args))
        self.run = AsyncMock(return_value={"query": "Example", "sources": [], "response": "Search only."})
        self.search = load_endpoint("search_media", {
            "parse_search": media.parse_search, "run_media_search": self.run,
            "HomeAssistantError": type("HomeAssistantError", (Exception,), {})})

    def test_search_only_passes_a_validated_title_to_the_adapter(self):
        complete(self.search(self.hass, self.connection, {"id": 1, "query": "  Example  "}))
        request = self.run.await_args.args[1]
        self.assertEqual(request["query"], "Example")
        self.assertEqual(request["kind"], "media_search")
        self.assertFalse(self.hass.data["jarvis_local"]["media_search_busy"])
        self.assertEqual(self.results[0][0], 1)

    def test_blank_oversized_and_device_clauses_run_nothing(self):
        for title in ("", " ", "x" * 201, "Example and turn off the lights"):
            complete(self.search(self.hass, self.connection, {"id": 1, "query": title}))
        self.run.assert_not_awaited()
        self.assertEqual(len(self.errors), 4)
        self.assertEqual(self.results, [])

    def test_busy_request_does_not_reset_another_search(self):
        self.hass.data["jarvis_local"]["media_search_busy"] = True
        complete(self.search(self.hass, self.connection, {"id": 1, "query": "Example"}))
        self.run.assert_not_awaited()
        self.assertTrue(self.hass.data["jarvis_local"]["media_search_busy"])
        self.assertEqual(self.errors[0][1], "busy")

    def test_public_info_contains_no_catalogue_token(self):
        token = "private_test_token_1234567890"
        self.hass.data["jarvis_local"]["media_search_config"] = config.validate({"tmdb_token": token})
        info = load_endpoint("info", {
            "ar": types.SimpleNamespace(async_get=lambda hass: types.SimpleNamespace(async_list_areas=lambda: [])),
            "public_profiles": lambda value: {}, "public_media_search": config.public_config})
        info(self.hass, self.connection, {"id": 1})
        payload = self.results[0][1]
        self.assertTrue(payload["media_search_config"]["catalogue_configured"])
        self.assertNotIn(token, json.dumps(payload))
        self.assertNotIn("tmdb_token", json.dumps(payload))

    def test_new_endpoints_keep_administrator_authorization(self):
        tree = ast.parse((ROOT / "websocket.py").read_text(encoding="utf-8"))
        for name in ("search_media", "save_media_search"):
            fn = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == name)
            def require_admin(handler):
                async def guarded(hass, connection, msg):
                    if not connection.is_admin:
                        connection.send_error(msg["id"], "unauthorized", "Administrator required")
                        return
                    return await handler(hass, connection, msg)
                return guarded
            namespace = {
                "websocket_api": types.SimpleNamespace(require_admin=require_admin,
                    websocket_command=lambda schema: lambda fn: fn, async_response=lambda fn: fn),
                "vol": types.SimpleNamespace(Required=lambda key: key),
                "parse_search": media.parse_search, "run_media_search": self.run,
                "save_media_search_config": AsyncMock(),
            }
            exec(compile(ast.Module(body=[fn], type_ignores=[]), "<authorized handler>", "exec"), namespace)
            self.connection.is_admin = False
            complete(namespace[name](self.hass, self.connection, {"id": 1, "query": "Example", "config": {}}))
        self.assertEqual([error[1] for error in self.errors], ["unauthorized", "unauthorized"])
        self.run.assert_not_awaited()


class CatalogueTransport(unittest.TestCase):
    def test_token_is_header_only_and_redirects_and_body_size_are_bounded(self):
        calls = []
        class Content:
            async def read(self, limit):
                calls.append(("read_limit", limit))
                return b'{"results":[]}'
        class Response:
            status = 200
            content = Content()
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        class Session:
            def get(self, url, **kwargs):
                calls.append((url, kwargs))
                return Response()
        helper = types.ModuleType("homeassistant.helpers.aiohttp_client")
        helper.async_get_clientsession = lambda hass: Session()
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.ClientTimeout = lambda **kwargs: kwargs
        with patch.dict(sys.modules, {"homeassistant.helpers.aiohttp_client": helper, "aiohttp": aiohttp}):
            result = complete(adapters._tmdb_json(object(), "private_read_token", "search/multi", {"query": "Example"}))
        url, request = calls[0]
        self.assertEqual(url, "https://api.themoviedb.org/3/search/multi")
        self.assertNotIn("private", url)
        self.assertEqual(request["headers"], {"Authorization": "Bearer private_read_token"})
        self.assertFalse(request["allow_redirects"])
        self.assertEqual(request["timeout"], {"total": 5})
        self.assertIn(("read_limit", 1_000_001), calls)
        self.assertEqual(result, {"results": []})


if __name__ == "__main__":
    unittest.main()
