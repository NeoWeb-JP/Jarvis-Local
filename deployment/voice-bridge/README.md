# Jarvis Voice Bridge deployment candidate

This is a versioned candidate, not a replacement applied to a live installation. Keep your current Assist pipeline and container while testing. Speaker profiles, recordings, database and models remain in VoicePipeline's persistent `/data` and `/models` mounts. Back these up before any migration; never publish them, authentication tokens or Home Assistant config.

## Read-only preflight

On the VoicePipeline host, run `sh check.sh voicepipeline`. Record the image identifier, mount paths and checksums. A TCP check in Jarvis Local only establishes that a port accepts connections, not that transcription or speaker matching is working.

The supplied Wyoming patch is based on the upstream `wyoming_server.py` SHA-256 `973fa024b093aa3623fe97c6ec48eb2b7feba8f65f01f6fc7ffa0e372b94ba2d`. The supplied speaker patch is the experimental cache implementation; it has not been validated across different image versions. These files are version-locked source overlays, not a universal upgrade mechanism. Do not install either on a different image without comparing the underlying source, including existing local changes. The installed threshold correction (`row[0]`) must be retained; check before deployment.

## Prepare a reviewable candidate

`sh stage-overrides.sh voicepipeline /path/to/new-staging-directory` checks the running container image ID and both active source hashes against the verified candidate, then copies the patches and writes a Compose override in a **new** directory. It does not start, stop or change the live container. Existing folders are never overwritten. A changed image or source is rejected, including when the source might otherwise be compatible.

The generated override is for review only: Compose volume merging and an image update can change what will actually run. Do not apply it alongside the old source-mount overrides. Before any cutover, back up the Compose files and data, examine `docker compose config`, verify that its resolved image is still the pinned image ID and that the existing `/data` and `/models` mounts are intact, and test on an isolated instance. The check does not prevent a future image tag being repointed between verification and deployment.

## Home Assistant bridge

The included integration retains the existing `jarvis_voice_bridge` domain and unique IDs. Its STT entity's friendly name has been changed, but existing registry names and IDs may remain unchanged. It is not installed by Jarvis Local's HACS update. To trial it, first back up `/config/custom_components/jarvis_voice_bridge` and Home Assistant configuration, then copy the candidate directory into an isolated Home Assistant test instance. Restart and test STT with the diagnostic conversation entity, followed by Jarvis Local. Do not configure two live bridges against copied production enrollment data without understanding that both process audio.

## Verify and rollback

Use a test pipeline and confirm: readable transcription; matched and unknown speakers; two concurrent identical utterances on different devices; and neutral behaviour if identity is absent. The metadata travels in an in-process Python string subclass, which depends on Home Assistant internals and may stop carrying identity after an update. Never use speaker recognition for authorisation.

For rollback on the test instance, restore the backed-up bridge directory and restart Home Assistant. For container rollback, restore the previous compose overrides and image, then recreate the container with the same compose file set. Do not delete `/data`, `/models` or the current service. The read-only check script does not modify or install anything.

## Recreate an isolated test instance

`sh create-isolated.sh` is for a fresh test, not for replacing a running test. It refuses an existing `voicepipeline-isolated-test` container or `/opt/voicepipeline-isolated-test` directory, checks the verified live image and source hashes, copies the data and models, takes a consistent SQLite snapshot and disables the webhook in that snapshot, then starts the test on ports 10301 and 8001. Run `check-isolation.sh` and inspect logs before testing. If any step fails, the newly created directory may be incomplete; inspect it before removing or retrying. The audio files are copied while the live system runs, so clips created or removed during the copy may not match the database snapshot; this is a test copy, not a production backup. The test container does not inherit the live container environment, so verify its models and integrations separately.

To stop the isolated service without affecting production, run `docker stop voicepipeline-isolated-test`. To start that same test again, run `docker start voicepipeline-isolated-test`. Neither command deletes the test data. Rollback of a production cutover remains a separate, untested procedure.
