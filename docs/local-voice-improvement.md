# Local XTTS voice improvement plan

## Licensing and consent boundary

The existing ElevenLabs cache is for **playback only**. Do not export it as
training material, build a model training job from it, or mix it into a local
speaker-reference set without documented permission from the service provider.
Generated audio does not become unrestricted training data merely because it
was downloaded or cached.

Use **original recordings of the consenting speaker** for any local XTTS
conditioning or future fine-tuning. Confirm consent to record, retain and
synthesise the voice, including use in household announcements.

## Recording and evaluation workflow

1. Retain the known-good current local XTTS profile (Profile B) unchanged.
2. With speaker consent, capture clean microphone recordings in a quiet room:
   separate files covering neutral sentences, questions, dynamic number and
   weather phrases, South African terms and playful/sarcastic delivery.
3. Keep raw recordings and transcripts in a private, non-GitHub folder with
   restrictive permissions and a clear deletion mechanism.
4. Validate sample rate, clipping, noise, channel count and accurate
   transcriptions. Reject bad or noisy clips rather than training on them.
5. Compare voice conditioning on withheld utterances before attempting
   fine-tuning. The GTX 1650 4GB is appropriate to continue running current
   XTTS inference, but may be insufficient for practical XTTS fine-tuning.
6. Fine-tune only with authorised original recordings and appropriate
   hardware. Evaluate intelligibility, voice similarity and latency against
   the current Profile B before promoting a new profile.
7. Keep Profile B as rollback; increment the voice-cache revision when the
   actual local voice changes.

## Preferred voice metric

`VoiceUsage` counts generated and cached responses by actual provider.
Preferred voice percentage is the proportion returned by the ElevenLabs
provider, including suitable category-cached alternatives. Metrics are
**in-memory and reset on integration reload/restart**; no speech contents,
user identity or API secrets are retained.

Next implementation steps: expose authorised read-only stats through HA,
persist aggregates if wanted, add explicit profile management, and
validate all TTS behaviours in Home Assistant before a release.

## Important

The new category-fallback code currently relies on catalogue exact-text
matches. Responses assembled dynamically or transformed by a phonetic
dictionary may not qualify. Never replace weather, temperature, time,
security, or other factual content with a semantically different cached
response merely to preserve the voice.
