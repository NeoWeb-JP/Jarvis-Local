# Jarvis Voice Bridge deployment candidate

This is a versioned candidate, not a replacement applied to a live installation. Keep your current Assist pipeline and container while testing. Speaker profiles, recordings, database and models remain in VoicePipeline's persistent `/data` and `/models` mounts. Back these up before any migration; never publish them, authentication tokens or Home Assistant config.

## Read-only preflight

On the VoicePipeline host, run `sh check.sh voicepipeline`. Record the image identifier, mount paths and checksums. A TCP check in Jarvis Local only establishes that a port accepts connections, not that transcription or speaker matching is working.

The supplied Wyoming patch is based on the upstream `wyoming_server.py` SHA-256 `973fa024b093aa3623fe97c6ec48eb2b7feba8f65f01f6fc7ffa0e372b94ba2d`. The supplied speaker patch is the experimental cache implementation; it has not been validated across different image versions. These files are version-locked source overlays, not a universal upgrade mechanism. Do not install either on a different image without comparing the underlying source, including existing local changes. The installed threshold correction (`row[0]`) must be retained; check before deployment.

## Home Assistant bridge

The included integration retains the existing `jarvis_voice_bridge` domain and unique IDs. Its STT entity's friendly name has been changed, but existing registry names and IDs may remain unchanged. It is not installed by Jarvis Local's HACS update. To trial it, first back up `/config/custom_components/jarvis_voice_bridge` and Home Assistant configuration, then copy the candidate directory into an isolated Home Assistant test instance. Restart and test STT with the diagnostic conversation entity, followed by Jarvis Local. Do not configure two live bridges against copied production enrollment data without understanding that both process audio.

## Verify and rollback

Use a test pipeline and confirm: readable transcription; matched and unknown speakers; two concurrent identical utterances on different devices; and neutral behaviour if identity is absent. The metadata travels in an in-process Python string subclass, which depends on Home Assistant internals and may stop carrying identity after an update. Never use speaker recognition for authorisation.

For rollback on the test instance, restore the backed-up bridge directory and restart Home Assistant. For container rollback, restore the previous compose overrides and image, then recreate the container with the same compose file set. Do not delete `/data`, `/models` or the current service. The read-only check script does not modify or install anything.
