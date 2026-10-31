"""Read-only media search, configuration, routing, and provider contract tests."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "jarvis_local"
package = types.ModuleType("_media_search_tests")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
media = importlib.import_module(package.__name__ + ".media_search")
config = importlib.import_module(package.__name__ + ".media_search_config")
adapters = importlib.import_module(package.__name__ + ".media_search_adapters")
understanding = importlib.import_module(package.__name__ + ".understanding")


def complete(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("A mocked read unexpectedly suspended")


async def immediate_wait(awaitable, seconds=8):
    return await awaitable


class Parsing(unittest.TestCase):
    def test_movie_context_is_one_read_only_search(self):
        request = media.parse_search("start movie time and play Desperate house wives")
        self.assertEqual(request["kind"], "media_search")
        self.assertEqual(request["query"], "Desperate house wives")
        self.assertTrue(request["movie_context"])

    def test_search_phrases_and_year(self):
        for phrase in ("find Desperate Housewives", "where can I watch Desperate Housewives",
                       "search my media library for Desperate Housewives", "watch Desperate Housewives",
                       "play the series Desperate Housewives", "look for Desperate Housewives"):
            with self.subTest(phrase=phrase):
                self.assertEqual(media.parse_search(phrase)["query"], "Desperate Housewives")
        self.assertEqual(media.parse_search("find The Office (2001)")["year"], 2001)
        self.assertEqual(media.parse_search("find The Office from 2001")["year"], 2001)
        self.assertEqual(media.parse_search("find Blade Runner 2049")["query"], "Blade Runner 2049")
        self.assertIsNone(media.parse_search("find Wonder Woman 1984")["year"])
        self.assertTrue(media.parse_search("preview find Desperate Housewives")["preview"])

    def test_music_negation_titles_and_compounds(self):
        for text in ("play country music", "pause music", "don't watch The Office", "start movie time"):
            self.assertIsNone(media.parse_search(text))
        self.assertEqual(media.parse_search("find Pride and Prejudice")["query"], "Pride and Prejudice")
        self.assertEqual(media.parse_search("find Dr. No")["query"], "Dr. No")
        self.assertEqual(media.parse_search("find Movie 43")["query"], "Movie 43")
        self.assertEqual(media.parse_search('find "The Show Must Go On"')["query"], "The Show Must Go On")
        with self.assertRaises(ValueError):
            media.parse_search("find The Office and turn off the lights")
        with self.assertRaises(ValueError):
            media.parse_search("find " + "x" * 201)

    def test_split_words_are_title_equivalent_but_other_titles_are_not(self):
        self.assertEqual(media.title_match("Desperate house wives", "Desperate Housewives"), "exact")
        self.assertEqual(media.title_match("Desperate Housewives", "Desperate Housewives S01E01.mkv"), "exact")
        self.assertEqual(media.title_match("The Office", "The Office (2001)"), "exact")
        self.assertIsNone(media.title_match("House", "Desperate Housewives"))
        self.assertIsNone(media.title_match("The Office", "The Lord of the Rings"))

    def test_conversational_wrappers_preserve_negation_and_titles(self):
        cases = {
            "Hey Declan, could you please turn the office light on for me please": "turn the office light on",
            "Would you mind turning the office light off please": "turn the office light off",
            "Declan, preview could you switch the kitchen off": "preview switch the kitchen off",
            "Um, Declan, put the kitchen lights off": "turn the kitchen lights off",
            "make the kitchen lights brighter": "brighten the kitchen lights",
            "Declan, could you not turn the office on": "not turn the office on",
            "find Please": "find Please",
            "find No Country for Old Men": "find No Country for Old Men",
            "find Finding Nemo": "find Finding Nemo",
            "Finding Nemo": "Finding Nemo",
        }
        for text, expected in cases.items():
            self.assertEqual(understanding.normalize_request(text)[0], expected)


class SourceAdapters(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        async def executor(fn, *args):
            return fn(*args)
        self.hass = types.SimpleNamespace(
            data={"jarvis_local": {}},
            config=types.SimpleNamespace(media_dirs={"local": str(self.folder)}),
            config_entries=types.SimpleNamespace(async_entries=lambda domain: []),
            async_add_executor_job=executor)
        self.wait_patch = patch.object(adapters, "_wait", immediate_wait)
        self.wait_patch.start()
        self.addCleanup(self.wait_patch.stop)

    def test_local_video_and_series_names_are_searched_without_reading_contents(self):
        (self.folder / "Desperate Housewives").mkdir()
        (self.folder / "Desperate Housewives" / "Desperate Housewives S01E01.mkv").write_bytes(b"private content")
        (self.folder / "Desperate Housewives.jpg").write_bytes(b"not a video")
        report = complete(adapters.search_local(self.hass, "Desperate house wives", None))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["matches"]), 2)
        self.assertEqual(report["matches"][0]["kind"], "folder")
        self.assertTrue(report["matches"][0]["contains_video"])
        self.assertTrue(all(item["match"] == "exact" for item in report["matches"]))
        self.assertNotIn(str(self.folder), str(report))
        self.assertNotIn("private content", str(report))

    def test_absent_or_unreadable_ha_library_is_not_reported_as_not_found(self):
        self.hass.config.media_dirs = {}
        self.assertEqual(complete(adapters.search_local(self.hass, "Example", None))["status"], "not_configured")
        self.hass.config.media_dirs = {"local": str(self.folder / "missing")}
        report = complete(adapters.search_local(self.hass, "Example", None))
        self.assertEqual(report["status"], "partial")

    def test_local_scan_deadline_is_reported_as_partial(self):
        (self.folder / "Example.mkv").write_bytes(b"video")
        with patch.object(adapters, "monotonic", side_effect=[0, 6]):
            report=adapters._scan_local({"local":str(self.folder)},"Example",None)
        self.assertEqual(report["status"],"partial")
        self.assertEqual(report["matches"],[])

    def test_connected_jellyfin_session_and_split_word_retry(self):
        calls = []
        def library(**kwargs):
            calls.append(kwargs)
            return {"Items": []} if kwargs["term"] != "Desperate" else {
                "Items": [{"Name": "Desperate Housewives", "ProductionYear": 2004, "Type": "Series"}]}
        entry = types.SimpleNamespace(runtime_data=types.SimpleNamespace(
            api_client=types.SimpleNamespace(jellyfin=types.SimpleNamespace(search_media_items=library))))
        self.hass.config_entries.async_entries = lambda domain: [entry]
        report = complete(adapters.search_jellyfin(self.hass, "Desperate house wives", None))
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["matches"][0]["match"], "exact")
        self.assertEqual(calls[0]["media"], "Movie,Series")
        self.assertEqual(len(calls), 2)

    def test_jellyfin_failures_and_unloaded_sessions_are_not_absence(self):
        entry = types.SimpleNamespace(runtime_data=None)
        self.hass.config_entries.async_entries = lambda domain: [entry]
        self.assertEqual(complete(adapters.search_jellyfin(self.hass, "Example", None))["status"], "unavailable")
        def fail(**kwargs):
            raise OSError("https://private-server/?api_key=secret")
        entry.runtime_data = types.SimpleNamespace(api_client=types.SimpleNamespace(
            jellyfin=types.SimpleNamespace(search_media_items=fail)))
        report = complete(adapters.search_jellyfin(self.hass, "Example", None))
        self.assertEqual(report["status"], "unavailable")
        self.assertNotIn("secret", str(report))
        self.assertNotIn("private-server", str(report))

    def test_priority_order_stops_on_exact_local_match(self):
        local = AsyncMock(return_value=adapters._source("Home Assistant media", "complete",
                         matches=[{"title": "Example", "kind": "movie", "match": "exact"}]))
        jellyfin, streaming = AsyncMock(), AsyncMock()
        with patch.object(adapters, "search_local", local), patch.object(adapters, "search_jellyfin", jellyfin), patch.object(adapters, "search_streaming", streaming):
            report = complete(adapters.search(self.hass, {"query": "Example"}))
        jellyfin.assert_not_awaited()
        streaming.assert_not_awaited()
        self.assertIn("Search only", report["response"])

    def test_empty_matching_folder_does_not_block_other_sources(self):
        (self.folder / "Desperate Housewives").mkdir()
        jellyfin=AsyncMock(return_value=adapters._source("Jellyfin","complete"))
        streaming=AsyncMock(return_value={"status":"not_configured","message":"Not checked","matches":[]})
        with patch.object(adapters,"search_jellyfin",jellyfin),patch.object(adapters,"search_streaming",streaming):
            report=complete(adapters.search(self.hass,{"query":"Desperate Housewives"}))
        jellyfin.assert_awaited_once()
        streaming.assert_awaited_once()
        self.assertIn("no video file was confirmed",report["response"])

    def test_all_sources_checked_in_order_when_unresolved(self):
        order = []
        async def local(*args):
            order.append("local")
            return adapters._source("Home Assistant media", "unavailable", "Could not check")
        async def jellyfin(*args):
            order.append("jellyfin")
            return adapters._source("Jellyfin", "complete")
        async def streaming(*args):
            order.append("streaming")
            return {"status": "not_configured", "message": "Not checked", "matches": []}
        with patch.object(adapters, "search_local", local), patch.object(adapters, "search_jellyfin", jellyfin), patch.object(adapters, "search_streaming", streaming):
            report = complete(adapters.search(self.hass, {"query": "Example"}))
        self.assertEqual(order, ["local", "jellyfin", "streaming"])
        self.assertIn("justwatch.com/uk/search", report["recommendation_url"])
        self.assertIn("Could not check", report["response"])


class Streaming(unittest.TestCase):
    def setUp(self):
        self.hass = types.SimpleNamespace(data={"jarvis_local": {"media_search_config": {
            "region": "GB", "subscriptions": list(media.SUBSCRIPTIONS),
            "tmdb_token": "private_test_read_token_1234567890"}}})
        self.candidate = {"id": 693, "media_type": "tv", "name": "Desperate Housewives", "first_air_date": "2004-10-03"}

    def test_subscriptions_rentals_addons_and_attribution_are_distinct(self):
        payload = {"results": {"GB": {
            "link": "https://www.themoviedb.org/tv/693/watch?locale=GB",
            "flatrate": [{"provider_name": "Disney Plus"}, {"provider_name": "Paramount+ Amazon Channel"}],
            "rent": [{"provider_name": "Amazon Video"}],
            "buy": [{"provider_name": "Apple TV"}]}}}
        api = AsyncMock(side_effect=[{"results": [self.candidate]}, payload])
        with patch.object(adapters, "_tmdb_json", api):
            result = complete(adapters.search_streaming(self.hass, "Desperate house wives", None))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["matches"][0]["selected_subscriptions"], ["Disney Plus"])
        self.assertIn("Paramount+ Amazon Channel (subscription)", result["matches"][0]["other_offers"])
        self.assertIn("Amazon Video (rent)", result["matches"][0]["other_offers"])
        self.assertEqual(result["attribution"], "JustWatch via TMDB")
        self.assertEqual(api.await_args_list[1].args[2], "tv/693/watch/providers")
        self.assertNotIn("private_test", str(result))

    def test_missing_credentials_never_claims_catalogue_was_checked(self):
        self.hass.data["jarvis_local"]["media_search_config"]["tmdb_token"] = ""
        with patch.object(adapters, "_tmdb_json", AsyncMock()) as api:
            result = complete(adapters.search_streaming(self.hass, "Example", None))
        api.assert_not_awaited()
        self.assertEqual(result["status"], "not_configured")

    def test_ambiguous_remakes_require_a_year(self):
        remake = {**self.candidate, "id": 694, "first_air_date": "2020-01-01"}
        api = AsyncMock(return_value={"results": [self.candidate, remake]})
        with patch.object(adapters, "_tmdb_json", api):
            result = complete(adapters.search_streaming(self.hass, "Desperate Housewives", None))
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(api.await_count, 1)
        self.assertEqual(len(result["candidates"]), 2)

    def test_provider_failure_is_unavailable_and_sensitive_text_is_not_exposed(self):
        api = AsyncMock(side_effect=OSError("secret token in private URL"))
        with patch.object(adapters, "_tmdb_json", api):
            result = complete(adapters.search_streaming(self.hass, "Example", None))
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret", str(result))
        self.assertEqual(result["matches"], [])

    def test_missing_uk_catalogue_is_not_global_absence(self):
        api = AsyncMock(side_effect=[{"results": [self.candidate]}, {"results": {"US": {
            "flatrate": [{"provider_name": "Netflix"}]}}}])
        with patch.object(adapters, "_tmdb_json", api):
            result = complete(adapters.search_streaming(self.hass, "Desperate Housewives", None))
        self.assertEqual(result["matches"][0]["selected_subscriptions"], [])
        report = {"query": "Desperate Housewives", "sources": [], "streaming": result}
        self.assertIn("not proof", media.summarize(report))

    def test_provider_links_are_restricted_to_expected_https_hosts(self):
        for url in ("javascript:alert(1)", "https://evil.example/path", "http://www.themoviedb.org/a",
                    "https://user:token@www.themoviedb.org/a"):
            self.assertIsNone(adapters._watch_link(url))
        self.assertEqual(adapters._watch_link("https://www.themoviedb.org/tv/1/watch"), "https://www.themoviedb.org/tv/1/watch")


class PrivateConfiguration(unittest.TestCase):
    def test_validation_and_public_settings_never_return_token(self):
        saved = config.validate({"tmdb_token": "test_token_that_is_long_enough"})
        public = config.public_config(types.SimpleNamespace(data={"jarvis_local": {"media_search_config": saved}}))
        self.assertEqual(public["region"], "GB")
        self.assertTrue(public["catalogue_configured"])
        self.assertNotIn("tmdb_token", public)
        self.assertEqual(config.validate({}, saved)["tmdb_token"], saved["tmdb_token"])
        self.assertEqual(config.validate({"clear_token": True}, saved)["tmdb_token"], "")
        for bad in ({"region": "US"}, {"subscriptions": ["unknown"]}, {"subscriptions": ["prime", "prime"]},
                    {"tmdb_token": "bad token"}, {"clear_token": True, "tmdb_token": saved["tmdb_token"]}):
            with self.assertRaises(ValueError):
                config.validate(bad, saved)

    def test_private_configuration_persists_and_activates_without_reload(self):
        stored = {}
        storage = types.ModuleType("homeassistant.helpers.storage")
        class Store:
            def __init__(self, *args): pass
            async def async_load(self): return dict(stored) if stored else None
            async def async_save(self, data): stored.update(data)
        storage.Store = Store
        hass = types.SimpleNamespace(data={})
        with patch.dict(sys.modules, {"homeassistant.helpers.storage": storage}):
            complete(config.save(hass, {"tmdb_token": "test_token_that_is_long_enough", "subscriptions": ["disney"]}))
            loaded = complete(config.load(hass))
        self.assertEqual(loaded["tmdb_token"], "test_token_that_is_long_enough")
        self.assertEqual(loaded["subscriptions"], ["disney"])
        self.assertEqual(hass.data["jarvis_local"]["media_search_config"], loaded)


if __name__ == "__main__":
    unittest.main()
