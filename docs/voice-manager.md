# Jarvis Voice Manager: persistent cache and fallback

## Configuration

The integration provides a Jarvis Voice Manager TTS entity. It uses the
existing Home Assistant TTS integrations, not an additional ElevenLabs API key.

Default providers:
- **Primary:** `tts.elevenlabs_text_to_speech`
- **Fallback:** `tts.jarvis_xtts` (the existing GPU XTTS Home Assistant entity)

The entity can be tested after deploying the updated source and restarting
Home Assistant. Do not switch the Muse Assist pipeline until manual speech
generation succeeds.

## Cache

Audio is stored persistently at `/config/jarvis_voice_cache` (outside the
GitHub-managed custom component). For each request, the manager:

1. Checks a format-aware cache keyed by exact text, provider, revision,
   language and synthesis options.
2. On miss, asks Home Assistant's provider TTS media-source API for audio
   with its own built-in cache enabled, and stores valid audio atomically.
3. If ElevenLabs generation fails, tries the **separate** XTTS cache/provider.
4. Never mixes the fallback voice into the ElevenLabs cache.

Identical concurrent requests are coalesced for a single manager instance.
Cached recordings can be used even if ElevenLabs is temporarily offline.

**Important:** The provider voice/model currently configured in Home
Assistant is not directly discoverable from this cache's metadata.
Change `hass.data['jarvis_local']['voice_cache_revision']` to a new value
if you change voices or ElevenLabs synthesis settings, or remove the
cache directory, to avoid returning recordings in the previous voice.
A proper settings UI for this value is still required.

## Outstanding work

- Validate against the installed Home Assistant version (entity registration,
  ElevenLabs media-source output and Muse playback).
- Verify fallback entity `tts.jarvis_xtts` actually exists and works.
- Add a settings/config-flow UI for provider IDs, cache revision, retention,
  size limits, and usage statistics.
- Confirm provider failures beyond the handled exceptions and TTS format
  compatibility. Test failed and concurrent generations end-to-end.
- Add ElevenLabs budget/usage controls and catalogue pre-generation.
- Avoid assuming saved audio is encrypted: treat the cache as private
  household data and exclude it from public repositories.

## Deploy/test

1. Update Jarvis Local from GitHub main using your chosen deployment method.
2. Restart Home Assistant and confirm Jarvis Voice Manager exists.
3. Use a manual TTS test with a short phrase; verify ElevenLabs playback.
4. Repeat the exact phrase and confirm a hit via debug logs and no new
   ElevenLabs usage. Check files under `/config/jarvis_voice_cache`.
5. Test fallback by temporarily making ElevenLabs unavailable without
   clearing its cache and using a **new uncached phrase**.
6. Once verified, select Jarvis Voice Manager in the Assist pipeline.
7. Rollback: reselect the previous ElevenLabs entity in Assist, then
   restore the previous Jarvis Local release if needed.

All changes currently sit on `main`, per owner preference. The owner
controls releases. No production Home Assistant deployment was performed.
