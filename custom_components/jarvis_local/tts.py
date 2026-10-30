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
from .phrase_library import PhraseLibrary, normalise_audio, phrase_parts

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROVIDER = "tts.elevenlabs_text_to_speech"
DEFAULT_FALLBACK = "tts.jarvis_xtts"


async def async_setup_entry(hass, entry, async_add_entities):
    cache = hass.data.setdefault("jarvis_local", {}).setdefault(
        "voice_cache", VoiceCache(hass.config.path("jarvis_voice_cache"))
    )
    usage = hass.data["jarvis_local"].setdefault("voice_usage", VoiceUsage())
    manager = JarvisVoiceManager(entry, cache, usage)
    hass.data['jarvis_local']['voice_manager'] = manager
    async_add_entities([manager])


class JarvisVoiceManager(TextToSpeechEntity):
    _attr_name = "Jarvis Voice Manager"
    _attr_has_entity_name = True
    _attr_supported_languages = ["en"]
    _attr_default_language = "en"

    def __init__(self, entry, cache, usage):
        self._attr_unique_id = f"{entry.entry_id}_voice_manager"
        self._entry = entry
        self._cache = cache
        self._usage = usage
        self._phrases = PhraseLibrary(cache, self._normalise)

    async def _normalise(self, extension, audio):
        from homeassistant.components.ffmpeg import get_ffmpeg_manager
        return await normalise_audio(extension, audio, get_ffmpeg_manager(self.hass).binary)

    async def prepare_phrase(self, text, kind):
        """Explicit admin generation; does not run any household action."""
        if kind not in {'clip', 'sentence'} or not isinstance(text, str) or not 1 <= len(text.strip()) <= 200:
            raise ValueError('Enter a phrase of 1 to 200 characters')
        config = self._entry.options
        if not config.get('cache_enabled', True):
            raise ValueError('Enable the voice cache in integration options first')
        state = await self._cache.snapshot(limit=0)
        if not state['storage_available']:
            raise ValueError('Cache limit or free-space reserve reached; no generation requested')
        provider = config.get('primary_tts', DEFAULT_PROVIDER)
        voice = config.get('elevenlabs_voice', '')
        options = {'voice': voice} if voice else {}
        identity = dict(provider=provider, voice_id=f"{config.get('cache_revision','v1')}:{voice}",
                        model=provider, language='en', settings=options)
        skipped_before = self._cache.skipped_writes
        async def generate(message):
            return await generate_from_existing_tts(self.hass, provider_entity_id=provider,
                                                     text=message, language='en', options=options)
        if kind == 'clip':
            extension, audio, hit = await self._phrases.clip(text.strip(), identity, generate)
        else:
            extension, audio, hit = await self._cache.get_or_generate_audio(
                text=text.strip(), **identity, generate=lambda:generate(text.strip()),
            )
        self._usage.record('elevenlabs_cached' if hit else 'elevenlabs_generated')
        return {'cached':hit, 'saved':hit or self._cache.skipped_writes == skipped_before,
                'extension':extension, 'bytes':len(audio)}

    async def async_get_tts_audio(self, message, language, options):
        config = self._entry.options
        primary = config.get("primary_tts", DEFAULT_PROVIDER)
        fallback = config.get("fallback_tts", DEFAULT_FALLBACK)
        # Bump these identity strings when the provider's configured voice
        # or model changes, otherwise old speech may be reused.
        revision = config.get("cache_revision", "v1")
        if not isinstance(revision, str) or not revision:
            raise HomeAssistantError("Invalid Jarvis voice-cache revision")
        if not isinstance(primary, str) or not primary.startswith("tts."):
            raise HomeAssistantError("Invalid primary TTS entity")
        if primary == self.entity_id or primary.startswith("tts.jarvis_voice_manager"):
            raise HomeAssistantError("Recursive Jarvis TTS provider")
        selected_voice = config.get("elevenlabs_voice", "")
        primary_options = dict(options or {})
        if selected_voice:
            primary_options["voice"] = selected_voice
        if not config.get("cache_enabled", True):
            _LOGGER.debug("Persistent cache disabled in settings")
        candidates = [primary]
        if isinstance(fallback, str) and fallback.startswith("tts.") and fallback not in candidates:
            candidates.append(fallback)

        errors = []
        for index, entity_id in enumerate(candidates):
            if entity_id == self.entity_id or entity_id.startswith("tts.jarvis_voice_manager"):
                continue
            try:
                provider_options = primary_options if index == 0 else dict(options or {})
                voice_key = f"{revision}:{selected_voice}" if index == 0 else revision
                async def request_audio(text=message, entity_id=entity_id, provider_options=provider_options):
                    return await generate_from_existing_tts(
                        self.hass, provider_entity_id=entity_id,
                        text=text, language=language, options=provider_options,
                    )
                if config.get("cache_enabled", True):
                    identity = dict(provider=entity_id, voice_id=voice_key, model=entity_id,
                                    language=language or 'en', settings=provider_options)
                    # Prefer a deliberately generated, natural whole sentence.
                    if index == 0 and config.get('phrase_library_enabled', True) and phrase_parts(message):
                        whole = await self._cache.find_cached_audio(text=message, **identity)
                        if whole:
                            self._usage.record('elevenlabs_cached')
                            return whole
                        try:
                            composed = await self._phrases.compose(message, identity, request_audio)
                        except (ValueError, OSError, TimeoutError) as err:
                            _LOGGER.warning('Phrase assembly unavailable; using whole-sentence TTS: %s', type(err).__name__)
                        else:
                            extension, audio, hit, generated = composed
                            self._usage.record('elevenlabs_phrase_cached' if hit or not generated else 'elevenlabs_phrase_generated')
                            self._usage.record_clips(generated)
                            return extension, audio
                    extension, audio, hit = await self._cache.get_or_generate_audio(
                    text=message,
                    provider=entity_id,
                    voice_id=voice_key,
                    model=entity_id,
                    language=language or "en",
                    settings=provider_options,
                    generate=request_audio,
                    )
                else:
                    extension, audio = await request_audio()
                    hit = False
                self._usage.record(("elevenlabs_" if index == 0 else "xtts_") + ("cached" if hit else "generated"))
                _LOGGER.debug("Jarvis TTS cache %s for %s", "hit" if hit else "miss", entity_id)
                return extension, audio
            except (HomeAssistantError, ValueError, OSError, TimeoutError) as err:
                _LOGGER.warning("Jarvis TTS provider %s failed: %s", entity_id, err)
                errors.append(f"{entity_id}: {type(err).__name__}")
                if index == 0 and config.get("cache_enabled", True) and config.get("category_fallback", True):
                    # Only AFTER primary ElevenLabs generation fails: try an
                    # already-recorded, semantically equivalent approved line.
                    # This never calls a provider or weakens Guest privacy.
                    alternate = await self._cached_primary_alternative(
                        message, primary, f"{revision}:{selected_voice}", language or "en", primary_options,
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


