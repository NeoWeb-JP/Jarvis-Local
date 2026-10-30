# Home Voice Assistant 0.27.0: TTS options

## Changes
- Home Assistant integration Options flow, shown via Settings → Devices & Services → Home Voice Assistant → three-dot menu → Configure (or Options).
- Primary TTS entity, default `tts.elevenlabs_text_to_speech`.
- Fallback TTS entity, default `tts.jarvis_xtts`.
- ElevenLabs voice selector from the existing Home Assistant provider's supported voices. The saved value is its **voice ID**, not the display name. If voices cannot be enumerated, enter the voice ID manually.
- Enable/disable persistent audio caching and same-category cached alternatives.
- Cache revision string, default `v1`; change if provider settings change without an identifiable voice ID/model revision.
- Voice chosen through Options is passed to ElevenLabs as the `voice` TTS option and included in Jarvis's cache identity.
- Legacy `jarvis_local` domain and existing entity IDs remain unchanged for compatibility.

## Configure
After installing updated files and restarting Home Assistant:
1. Open Home Voice Assistant → 3 dots on integration entry → Configure.
2. Choose the primary and fallback TTS provider entities.
3. Choose **Declan - South African News** from ElevenLabs voice list (if offered). This is NOT the software/wake-word setting.
4. Enable persistent cache and category alternatives; leave revision at `v1` if the voice/profile has not changed since initial use.
5. In Assist, choose **Jarvis Voice Manager** for TTS. The earlier ElevenLabs voice dropdown may disappear, since voice is now set in the integration.
6. Test one unique phrase then repeat with Home Assistant outer TTS caching disabled to exercise manager cache.
7. Confirm cached voice and subsequent ElevenLabs credit usage before relying on fallback. If playback fails, switch Assist TTS back to the direct ElevenLabs entity.

## Limits
- Provider IDs are free-text entity IDs in this first version; voice picker is dynamic when HA exposes it.
- No account-level quota display, automatic model tracking or cache eviction yet.
- The broader Declan personality catalogue, generic integration migration and wake-word model deployment are separate tasks.
- No release tag is created automatically; owner publishes GitHub release.
