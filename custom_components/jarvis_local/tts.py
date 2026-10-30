"""Jarvis TTS: cached ElevenLabs with independent local XTTS fallback."""
from __future__ import annotations

import logging
import random
from pathlib import Path

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.exceptions import HomeAssistantError

from .voice_cache import VoiceCache
from .voice_catalog_fallback import category_alternatives, load_catalogue
from .voice_provider import generate_from_existing_tts
from .voice_usage import VoiceUsage

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROVIDER = "tts.elevenlabs_text_to_speech"
DEFAULT_FALLBACK = "tts.jarvis_xtts"


async def async_setup_entry(hass, entry, async_add_entities):
    cache = hass.data.setdefault("jarvis_local", {}).setdefault(
        "voice_cache", VoiceCache(hass.config.path("jarvis_voice_cache"))
    )
    usage = hass.data["jarvis_local"].setdefault("voice_usage", VoiceUsage())
    async_add_entities([JarvisVoiceManager(entry.entry_id, cache, usage)])


class JarvisVoiceManager(TextToSpeechEntity):
    _attr_name = "Jarvis Voice Manager"
    _attr_has_entity_name = True
    _attr_supported_languages = ["en"]
    _attr_default_language = "en"

    def __init__(self, entry_id, cache, usage):
        self._attr_unique_id = f"{entry_id}_voice_manager"
        self._cache = cache
        self._usage = usage

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
        for index, entity_id in enumerate(candidates):
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
                self._usage.record(("elevenlabs_" if index == 0 else "xtts_") + ("cached" if hit else "generated"))
                _LOGGER.debug("Jarvis TTS cache %s for %s", "hit" if hit else "miss", entity_id)
                return extension, audio
            except (HomeAssistantError, ValueError, OSError, TimeoutError) as err:
                _LOGGER.warning("Jarvis TTS provider %s failed: %s", entity_id, err)
                errors.append(f"{entity_id}: {type(err).__name__}")
                if index == 0:
                    # Only AFTER primary ElevenLabs generation fails: try an
                    # already-recorded, semantically equivalent approved line.
                    # This never calls a provider or weakens Guest privacy.
                    alternate = await self._cached_primary_alternative(
                        message, primary, revision, language or "en", options or {},
                    )
                    if alternate is not None:
                        self._usage.record("elevenlabs_category_cached")
                        return alternate

        raise HomeAssistantError("Jarvis TTS primary and fallback failed: " + "; ".join(errors))

    async def _cached_primary_alternative(
        self, message, provider, revision, language, options,
    ):
        try:
            catalogue = await self.hass.async_add_executor_job(
                load_catalogue, Path(__file__).with_name("responses.json"),
            )
        except (OSError, ValueError):
            _LOGGER.warning("Jarvis response catalogue unavailable; using normal fallback")
            return None

        guest = (
            self.hass.states.is_state("input_boolean.guest_mode", "on")
            or self.hass.states.is_state("input_boolean.jarvis_visitors_present", "on")
        )
        alternatives = list(category_alternatives(message, catalogue, guest=guest))
        random.shuffle(alternatives)
        for alternate in alternatives:
            cached = await self._cache.find_cached_audio(
                text=alternate, provider=provider, voice_id=revision,
                model=provider, language=language, settings=options,
            )
            if cached is not None:
                _LOGGER.info(
                    "Jarvis using approved cached %s alternative before local XTTS",
                    "Guest" if guest else "Home",
                )
                return cached
        return None
