"""Single-instance setup and voice settings options."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import tts

DOMAIN = "jarvis_local"
PRIMARY = "tts.elevenlabs_text_to_speech"
FALLBACK = "tts.jarvis_xtts"


class JarvisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Home Voice Assistant", data={})
        return self.async_show_form(step_id="user")

    async def async_step_import(self, user_input):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Home Voice Assistant", data={})

    @staticmethod
    def async_get_options_flow(config_entry):
        return VoiceOptionsFlow()


class VoiceOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        current = self.config_entry.options
        if user_input is not None:
            if user_input["primary_tts"] == user_input["fallback_tts"]:
                return self.async_show_form(
                    step_id="init", data_schema=self._schema(current),
                    errors={"base": "same_provider"},
                )
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._schema(current))

    def _schema(self, current):
        # Pull from the user's existing ElevenLabs integration without another
        # API key. Voice values are provider voice IDs, not display names.
        voice_choices = {}
        try:
            provider_id = current.get("primary_tts", PRIMARY)
            engine = tts.get_engine_instance(self.hass, provider_id)
            if engine is not None:
                supported = engine.async_get_supported_voices("en") or []
                voice_choices = {v.voice_id: v.name for v in supported}
        except (LookupError, AttributeError, ValueError):
            pass
        voice_id = current.get("elevenlabs_voice", "")
        schema = {
            vol.Required("primary_tts", default=current.get("primary_tts", PRIMARY)): str,
            vol.Required("fallback_tts", default=current.get("fallback_tts", FALLBACK)): str,
            vol.Required("cache_enabled", default=current.get("cache_enabled", True)): bool,
            vol.Required("phrase_library_enabled", default=current.get("phrase_library_enabled", True)): bool,
            vol.Required("category_fallback", default=current.get("category_fallback", True)): bool,
            vol.Required("cache_revision", default=current.get("cache_revision", "v1")): str,
        }
        if voice_choices:
            schema[vol.Required("elevenlabs_voice", default=voice_id if voice_id in voice_choices else next(iter(voice_choices)))] = vol.In(voice_choices)
        else:
            schema[vol.Optional("elevenlabs_voice", default=voice_id)] = str
        return vol.Schema(schema)


