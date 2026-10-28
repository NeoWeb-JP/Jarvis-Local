# Jarvis Local

A Home Assistant conversation integration with a sidebar chat interface and rule-based household commands. The conversation agent does not require an LLM. Speech recognition, speech output, music and device integrations use the providers configured in Home Assistant and may use cloud services.

## Current scope

This is an early prototype. Some features require existing helper entities and scripts. The voice and sidebar interface must be verified on your own Home Assistant installation.

Open **Jarvis settings** in the sidebar to select optional household entities. Settings are stored by Home Assistant and kept across HACS updates. Lights and areas are discovered automatically. A single thermostat can be discovered automatically; select one if there are several. Car sensors and custom scripts must be chosen because their roles cannot be inferred reliably from entity names alone. Switches used as lights require an explicit spoken name and must be exposed to Assist. Existing scripts, helpers and automations are not created or replaced by this integration.

If `/config/jarvis_local_settings.json` exists from version 0.9.2, its values are loaded until settings are saved in the interface. You can remove the old file after confirming your selections have been saved and survive a restart. Do not put household settings in the repository.

## Installation with HACS

1. Back up Home Assistant, including configuration and your existing custom integration.
2. In HACS, choose the three-dot menu, **Custom repositories**. Add `https://github.com/NeoWeb-JP/jarvis-local` as an **Integration**. This URL assumes that repository has been created and published.
3. Find Jarvis Local in HACS and download a released version. It installs files under `/config/custom_components/jarvis_local/`, replacing the manually installed integration files. Preserve any local edits first.
4. Restart Home Assistant. Keep the existing Jarvis config entry, Assist pipeline, scripts, helpers and automations. Do not create a duplicate config entry.
5. Test the sidebar on mobile and a few commands in chat and through the satellite. Select your existing Jarvis conversation entity in the Assist pipeline if needed.

For a fresh installation, add Jarvis Local under **Settings > Devices & services > Add integration** after restarting, then configure your Assist pipeline. Home-specific commands additionally require the corresponding existing scripts, entities and helpers.

## Updates and rollback

Back up before updating. Install an offered update in HACS or Home Assistant, restart Home Assistant, and refresh the browser or Companion app for sidebar changes. To roll back, select a previous HACS release if offered, restart and test. Restore the backup if the previous release is unavailable or settings need restoring. Verify the chosen conversation entity in your Assist pipeline afterwards.

## For the repository owner

Do not commit Home Assistant backups, secrets, access tokens, logs, or personal configuration.

For a release, verify changes, run the checks, increment the version in `manifest.json`, publish a GitHub release with a matching version tag and release notes, then test the offered HACS update on Home Assistant. GitHub Actions are supplied but must pass on the actual repository; they are not a substitute for live testing.

## Speaking and optional speaker identification

The microphone button records directly in the Jarvis sidebar and runs the selected Home Assistant Assist pipeline. In **Voice settings**, choose an assistant with Jarvis Local as its conversation agent and a speech-to-text engine. Tap the microphone again to finish speaking. The transcript and response appear in the chat, and the assistant's configured text-to-speech can play the reply. Microphone access requires browser permission and a secure connection. On some mobile browsers, audio playback can require user interaction. Voice requests use the voice assistant's context rather than the chat-room selector.

Voice and typed commands share the current conversation ID, but voice uses the selected Assist pipeline's configuration. If the pipeline uses the voice bridge, speaker identification remains available.

The experimental Jarvis Voice Bridge can pass a speaker match to Jarvis for a personalised good-morning response. Configure the bridge as the speech-to-text engine and Jarvis Local as the conversation agent in the same pipeline. Keep the bridge and its VoicePipeline server patch installed. In `/config/jarvis_voice_id.json`, define `profiles` using the exact enrolled speaker names in lower case, with a display `name` and `min_confidence` between 0 and 1. Restart Home Assistant after editing. This file stays local and must not be committed. If no profile matches or the score is too low, Jarvis replies without a name. Speaker matches are approximate and must never be used to grant access or authorise sensitive actions.

### Personal morning responses

The morning routine still runs its configured actions. Jarvis selects its spoken greeting separately so an unknown speaker does not receive a greeting written for someone else. Add an optional `morning_responses` list to a profile in `/config/jarvis_voice_id.json`; each string may use `{name}`. Profiles without a list use a general named greeting, and an unknown speaker gets a neutral response. Keep this personal configuration out of the repository. Restart Home Assistant after changing the file. Existing sentence-trigger automations can intercept phrases before this agent; disable any competing trigger if Jarvis does not receive the request.
