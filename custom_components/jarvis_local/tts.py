"""Jarvis TTS: cached ElevenLabs with independent local XTTS fallback."""
from __future__ import annotations

import logging

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.exceptions import HomeAssistantError

from .voice_cache import VoiceCache
from .voice_provider import generate_from_existing_tts

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROVIDER = "tts.elevenlabs_text_to_speech"
DEFAULT_FALLBACK = "tts.jarvis_xtts"


async def async_setup_entry(hass, entry, async_add_entities):
    cache = hass.data.setdefault("jarvis_local", {}).setdefault(
        "voice_cache", VoiceCache(hass.config.path("jarvis_voice_cache"))
    )
    async_add_entities([JarvisVoiceManager(entry.entry_id, cache)])


class JarvisVoiceManager(TextToSpeechEntity):
    _attr_name = "Jarvis Voice Manager"
    _attr_has_entity_name = True
    _attr_supported_languages = ["en"]
    _attr_default_language = "en"

    def __init__(self, entry_id, cache):
        self._attr_unique_id = f"{entry_id}_voice_manager"
        self._cache = cache

    async def async_get_tts_audio(self, message, language, options):
        config = self.hass.data.get("jarvis_local", {})
        primary = config.get("voice_provider_entity", DEFAULT_PROVIDER)
        fallback = config.get("voice_fallback_entity", DEFAULT_FALLBACK)
        # Bump these identity strings when the provider's configured voice
        # or model changes, otherwise old speech may be reused.
        revision = config.get("voice_cache_revision", "v1")
        if not isinstance(revision, str) or not revision:
            raise HomeAssistantError("Invalid Jarvis voice-cache revision")
        if not isinstance(primary, str) or not primary.startswith("tts."):
            raise HomeAssistantError("Invalid primary TTS entity")
        if primary == self.entity_id or primary.startswith("tts.jarvis_voice_manager"):
            raise HomeAssistantError("Recursive Jarvis TTS provider")
        candidates = [primary]
        if isinstance(fallback, str) and fallback.startswith("tts.") and fallback not in candidates:
            candidates.append(fallback)

        errors = []
        for entity_id in candidates:
            if entity_id == self.entity_id or entity_id.startswith("tts.jarvis_voice_manager"):
                continue
            try:
                extension, audio, hit = await self._cache.get_or_generate_audio(
                    text=message,
                    provider=entity_id,
                    voice_id=revision,
                    model=entity_id,
                    language=language or "en",
                    settings=options or {},
                    generate=lambda entity_id=entity_id: generate_from_existing_tts(
                        self.hass, provider_entity_id=entity_id,
                        text=message, language=language, options=options,
                    ),
                )
                _LOGGER.debug("Jarvis TTS cache %s for %s", "hit" if hit else "miss", entity_id)
                return extension, audio
            except (HomeAssistantError, ValueError, OSError, TimeoutError) as err:
                _LOGGER.warning("Jarvis TTS provider %s failed: %s", entity_id, err)
                errors.append(f"{entity_id}: {type(err).__name__}")

        raise HomeAssistantError("Jarvis TTS primary and fallback failed: " + "; ".join(errors))
