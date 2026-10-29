"""Jarvis Voice Manager TTS entity.

Delegates to the user's existing ElevenLabs TTS entity, so no duplicate API
key is needed. HA's TTS media-source cache is enabled for provider calls.
"""
from __future__ import annotations

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.exceptions import HomeAssistantError

from .voice_provider import generate_from_existing_tts

DEFAULT_PROVIDER = "tts.elevenlabs_text_to_speech"


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([JarvisVoiceManager(entry.entry_id)])


class JarvisVoiceManager(TextToSpeechEntity):
    _attr_name = "Jarvis Voice Manager"
    _attr_has_entity_name = True
    _attr_supported_languages = ["en"]
    _attr_default_language = "en"

    def __init__(self, entry_id):
        self._attr_unique_id = f"{entry_id}_voice_manager"

    async def async_get_tts_audio(self, message, language, options):
        provider_id = self.hass.data.get("jarvis_local", {}).get(
            "voice_provider_entity", DEFAULT_PROVIDER
        )
        if provider_id == self.entity_id:
            raise HomeAssistantError("Jarvis TTS cannot use itself as provider")
        extension, audio = await generate_from_existing_tts(
            self.hass, provider_entity_id=provider_id,
            text=message, language=language, options=options,
        )
        return extension, audio
