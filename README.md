# Jarvis Local

A Home Assistant conversation integration with a sidebar chat interface and rule-based household commands. The conversation agent does not require an LLM. Speech recognition, speech output, music and device integrations use the providers configured in Home Assistant and may use cloud services.

## Current scope

This is an early prototype. Some features require existing helper entities and scripts. The voice and sidebar interface must be verified on your own Home Assistant installation.

Optional household integrations are configured in `/config/jarvis_local_settings.json`, which is outside this repository and preserved across HACS updates. The JSON object may contain `thermostat`, `car_cable_sensor`, `car_battery_sensor`, `guest_mode`, `guest_names`, `music_script`, `personality_script`, `phonetic_script`, and a `switch_lights` object mapping spoken names to switch entity IDs. Values are entity IDs. Missing entries disable their corresponding features; lights and areas are discovered independently. Scripts and helpers are not created or replaced by this integration. Restart Home Assistant after changing the file. Keep backups and never commit the file to GitHub.

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
