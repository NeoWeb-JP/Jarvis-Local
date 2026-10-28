# Jarvis Voice Bridge

Home Assistant speech-to-text integration for a compatible Wyoming voice service carrying per-request speaker identification. The bridge is separate from Jarvis Local and does not require an LLM. Its diagnostic conversation entity can report whether identity reached the agent.

## Existing installation

Keep the existing `jarvis_voice_bridge` integration entry and speech-to-text entity in the Assist pipeline. Back up Home Assistant before replacing any manually installed custom integration. After an update, restart Home Assistant and confirm the same entity IDs remain selected. Home Assistant may retain a previous display name; rename it through the entity settings without changing the entity ID.

## Setup

After installing, add Jarvis Voice Bridge in Settings → Devices & Services and enter the host and Wyoming port. For personalised Jarvis responses, choose the bridge as speech-to-text and Jarvis Local as conversation agent in the same assistant. The service must send the `jarvis-speaker` event; an ordinary Wyoming service may provide text without identity.

The bridge's metadata relies on Home Assistant retaining an in-process string subclass, an implementation detail which may change in future Home Assistant versions. If metadata is lost, transcripts remain normal and identities must be treated as unknown. Never use speaker identification to authorise actions. VoicePipeline recordings, database and model files remain on the voice server; this integration does not update or back up them.

## Updates and rollback

Keep the previous bridge folder or a Home Assistant backup. After any change, test transcription, a recognised and unknown speaker, and concurrent requests. To roll back, restore the previous integration folder and restart Home Assistant. Do not replace VoicePipeline data as part of a bridge rollback.
