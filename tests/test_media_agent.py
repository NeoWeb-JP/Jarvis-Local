"""Actual agent integration: conversational input and search never start playback."""
import unittest
from dataclasses import dataclass, field
import types
import sys
from unittest.mock import AsyncMock, patch
import test_agent_dialogue as fixtures
from test_satellite_stop import immediate


class MediaAgent(unittest.TestCase):
    def setUp(self):
        self.hass = fixtures.fixtures.Hass()
        self.hass.data = {}
        self.hass.services = fixtures.Services()
        self.agent = fixtures.module.JarvisAgent(self.hass)
        self.report = {"query": "Desperate Housewives", "region": "GB", "sources": [],
                       "streaming": {"status": "complete", "matches": []},
                       "response": "Search results. Search only. I have not started movie time or played anything."}
        self.search = AsyncMock(return_value=self.report)
        replacement = patch.object(fixtures.module, "search_media", self.search)
        replacement.start()
        self.addCleanup(replacement.stop)
        verification=patch.object(sys.modules["jarvis_test.device_control"],"verify",fixtures.verify)
        verification.start()
        self.addCleanup(verification.stop)

    @immediate
    async def test_compound_movie_request_is_one_search_with_no_routine_or_playback(self):
        self.hass.states.values["script.jarvis_local_movie"] = fixtures.fixtures.State(
            "script.jarvis_local_movie", "Movie routine", "off")
        reply = await self.agent.async_handle(fixtures.UserInput(
            "Hey Declan, could you please start movie time and play Desperate house wives"))
        self.search.assert_awaited_once()
        request = self.search.await_args.args[1]
        self.assertEqual(request["query"], "Desperate house wives")
        self.assertEqual(self.hass.services.calls, [])
        self.assertIn("Search only", reply.response.speech)
        self.assertEqual(reply.response.extra_data["jarvis_local"]["media_search"], self.report)
        self.assertFalse(reply.response.extra_data["jarvis_local"]["trackable"])

    @immediate
    async def test_preview_does_not_search_or_run_any_actions(self):
        reply = await self.agent.async_handle(fixtures.UserInput(
            "Declan, preview could you find Desperate Housewives"))
        self.search.assert_not_awaited()
        self.assertEqual(self.hass.services.calls, [])
        self.assertIn("Preview only", reply.response.speech)

    @immediate
    async def test_media_search_replaces_pending_light_dialogue(self):
        await self.agent.async_handle(fixtures.UserInput("lamp on"))
        self.assertTrue(self.agent._pending_clarifications)
        reply = await self.agent.async_handle(fixtures.UserInput("where can I watch Desperate Housewives"))
        self.assertFalse(self.agent._pending_clarifications)
        self.assertFalse(reply.continue_conversation)
        self.assertEqual(self.hass.services.calls, [])

    @immediate
    async def test_names_politeness_and_known_targets_work_without_fuzzy_execution(self):
        reply = await self.agent.async_handle(fixtures.UserInput(
            "Hey Declan, would you mind turning the office light on for me please"))
        self.assertEqual(self.hass.services.calls[0][0][:2], ("light", "turn_on"))
        self.assertEqual(self.hass.services.calls[0][0][2], {"entity_id": ["light.office"]})
        self.search.assert_not_awaited()
        self.hass.services.calls.clear()
        for text in ("Declan, could you not turn the office on", "Declan, offers life on",
                     "don't start movie time and play Desperate Housewives"):
            await self.agent.async_handle(fixtures.UserInput(text))
        self.assertEqual(self.hass.services.calls, [])
        self.search.assert_not_awaited()

    @immediate
    async def test_music_requests_still_use_existing_music_path(self):
        self.hass.data = {"jarvis_local": {"settings": {"music_script": "script.music"}}}
        self.hass.states.values["script.music"] = fixtures.fixtures.State("script.music", "Music", "off")
        await self.agent.async_handle(fixtures.UserInput("play country music in kitchen"))
        self.search.assert_not_awaited()
        self.assertEqual(self.hass.services.calls[0][0][:2], ("script", "music"))

    @immediate
    async def test_weather_question_is_understood_without_household_actions(self):
        self.hass.data = {"jarvis_local": {"settings": {"weather": "weather.home"}}}
        weather = fixtures.fixtures.State("weather.home", "Weather", "partlycloudy")
        weather.attributes = {"temperature": 15, "temperature_unit": "C"}
        self.hass.states.values["weather.home"] = weather
        reply = await self.agent.async_handle(fixtures.UserInput("Declan, could you tell me the weather"))
        self.assertIn("15 C", reply.response.speech)
        self.assertEqual(self.hass.services.calls, [])
        self.search.assert_not_awaited()

    @immediate
    async def test_search_metadata_never_enables_replay_as_device_command(self):
        reply = await self.agent.async_handle(fixtures.UserInput("find Pride and Prejudice"))
        self.assertFalse(reply.response.extra_data["jarvis_local"]["trackable"])
        self.assertFalse(reply.continue_conversation)
        self.assertEqual(self.hass.services.calls, [])

    @immediate
    async def test_polite_declan_stop_remains_silent_and_satellite_scoped(self):
        self.hass.data={"jarvis_local":{"settings":{"satellite_media_players":{
            "assist_satellite.bedroom":"media_player.bedroom"}}}}
        user=fixtures.UserInput("Declan, could you be quiet please")
        user.satellite_id="assist_satellite.bedroom"
        reply=await self.agent.async_handle(user)
        self.assertEqual(reply.response.speech,"")
        self.assertEqual(self.hass.services.calls[0][0],
                         ("media_player","media_stop",{"entity_id":"media_player.bedroom"}))
        self.search.assert_not_awaited()

    @immediate
    async def test_satellite_only_voice_uses_existing_safe_off_recovery(self):
        @dataclass
        class Input:
            text: str
            language: str = "en"
            conversation_id: str = "one"
            satellite_id: str = "assist_satellite.bedroom"
            device_id: object = None
            context: object = field(default_factory=lambda: types.SimpleNamespace(user_id="user"))
        reply=await self.agent.async_handle(Input("office off. random background chatter"))
        self.assertEqual(len(self.hass.services.calls),1)
        self.assertEqual(self.hass.services.calls[0][0][:2],("light","turn_off"))
        self.assertNotIn("did not understand",reply.response.speech)
        self.hass.services.calls.clear()
        await self.agent.async_handle(Input("office off. no wait turn the kitchen on"))
        self.assertEqual(self.hass.services.calls,[])


if __name__ == "__main__":
    unittest.main()
