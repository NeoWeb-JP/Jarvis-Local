# Jarvis Voice Manager: implementation status

The initial code is on `main`, but **is not yet selectable as an Assist TTS engine**.

## What exists
- `voice_cache.py`: persistent, provider/model/voice/settings-aware audio byte cache; duplicate-call coalescing and atomic writes.
- `voice_provider.py`: asks Home Assistant's built-in TTS media-source API to generate/retrieve audio using an existing configured `tts.*` provider. Jarvis does **not** store an ElevenLabs API key.
- `tests/test_voice_cache.py`: cache behaviour tests (run these before releasing).

## Remaining integration
1. Confirm exact installed ElevenLabs TTS entity ID, language, configured voice and audio format from Home Assistant.
2. Add a proper `TextToSpeechEntity` platform (`tts.jarvis_voice_manager`) with a safe provider setting, avoiding recursive selection.
3. Since the provider selects its returned audio format dynamically, resolve the actual format BEFORE writing to the appropriately keyed persistent cache; preserve the precise returned bytes. Reject empty/unsupported audio.
4. Implement fallback to the existing XTTS server using an independently keyed voice profile. Fail clearly when no provider works.
5. Add cache statistics, eviction policy, and controls for pre-generation, including guest-safe catalogues.
6. Verify that selecting the entity in Assist successfully plays speech through both Muse satellites and that repeated speech makes no new ElevenLabs generation.
7. Check compatibility with the user's installed Home Assistant version before deployment.

## Deployment
Do not switch the production Assist TTS selector to a Jarvis entity until the platform and tests above are complete. Existing ElevenLabs and local XTTS configurations are unchanged by these files.
