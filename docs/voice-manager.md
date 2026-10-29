# Jarvis Voice Manager (development integration)

## Configured provider

The user's existing Home Assistant ElevenLabs provider is
`tts.elevenlabs_text_to_speech`. No additional ElevenLabs API key is required.

## What's implemented on main

- `tts.py` provides a new `TextToSpeechEntity` named **Jarvis Voice Manager**.
- `__init__.py` registers both the conversation and TTS platforms.
- `voice_provider.py` fetches actual audio from the existing ElevenLabs entity through Home Assistant's TTS media-source API with `cache=True`.
- `voice_cache.py` implements a separate persistent provider-independent cache, **not connected to the TTS entity yet**.
- The manifest now declares the Home Assistant TTS dependency.

### What this does and does not cache

The working TTS path currently relies on Home Assistant's built-in TTS
media-source cache. The independent `VoiceCache` is not yet used by this
entity. A subsequent implementation must verify whether provider-specific
options (voice/model) are included in the HA cache identity and connect
the independent cache if more control is needed.

## Not yet verified

- Compatible with the exact installed Home Assistant release and ElevenLabs
  integration implementation.
- Entity creation, allowed language tag, and Muse playback.
- Real caching measured against actual ElevenLabs account usage.
- Reliable local XTTS fallback, storage metrics and monthly credit limits.
- Independent format-aware cache and catalogue pre-generation.

## Test and release policy

Do not change the production Assist pipeline until the new entity appears
and can generate audio through a manual test. Keep the existing ElevenLabs
entity selected until validated. Verify no paid repeat generation by
comparing ElevenLabs usage, rather than assuming a cache hit.

These code changes are on `main` per the repository owner's request.
The owner handles GitHub Releases and deployment. No live Home Assistant
files have been modified.
