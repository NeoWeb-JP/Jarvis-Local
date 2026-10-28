# VoicePipeline speaker corrections and thresholds

This release candidate brings together two optional VoicePipeline changes that work alongside Jarvis Local and Jarvis Voice Bridge:

- **History correction:** change the assigned speaker or undo an assignment. Incorrect references for that recording are removed transactionally; audio and other recordings remain intact. Changes use a confirmation and reject stale browser views. The original pipeline match remains visible separately.
- **Per-speaker thresholds:** after choosing the highest-scoring speaker, VoicePipeline applies that speaker's configured threshold. A rejected best candidate becomes unknown; it is not replaced by another candidate. Missing per-speaker entries use the global threshold. Invalid threshold mappings reject matches rather than weakening the threshold.

These are VoicePipeline server changes, not Home Assistant integrations. Installing or upgrading a Jarvis Local or Jarvis Voice Bridge HACS release does not install or update them. Speaker recognition is approximate and must not be used to authorise actions.

## Source and version compatibility

- `history-correction/` contains an API and UI candidate derived from VoicePipeline under its included MIT licence. The candidate is tied to the upstream API and UI hashes listed in its README.
- `per-speaker-threshold/` contains the speaker-model candidate and synthetic tests. It is tied to the original speaker patch hash listed in its README. The threshold setting is `speaker_match_thresholds`, a JSON object in VoicePipeline's settings database. The regular VoicePipeline settings page does not manage this per-speaker mapping.
- The included deployment scripts are deliberately tied to a particular image, Compose arrangement and host paths. They refuse other arrangements rather than assuming compatibility. Use their preflight and review the actual environment; do not blindly apply them to another installation.
- A Compose deployment must retain **all** existing configuration files and both added app mounts. The generated wrapper includes the full file set. Keep the staged files available for as long as the container uses them.

## Behaviour and limitations

Correcting a History entry does not automatically add it to the newly assigned person's reference clips. It does not restore reference clips rotated out by earlier assignments or recalculate old interaction counts and confidence averages. An undo returns the entry to Pending. The speaker cache refresh is scheduled, so matching may temporarily use old references after a correction. A user can review and confirm suitable Pending clips separately.

The model needs sufficient speech to recognise someone reliably. A threshold change may increase matches and also increase incorrect matches; compare labelled examples from each person and keep unknown speakers neutral.

## Validation performed

Automated tests cover per-speaker threshold selection, invalid settings, corrections and undo with the upstream SQLite schema, stale requests and simultaneous corrections, simulated History UI actions, Compose configuration checks, and mocked deployment and rollback paths. They do not replace live Home Assistant or real-audio tests.

The isolated service was manually tested with recognised speakers and the History correction and undo flow. The production management page displayed the correction control and a normal voice request completed. Production correction writes have not been independently tested; use an isolated instance for destructive test cases.

## Manual test checklist

Use a separate test service and test data when changing assignments.

1. Check that the existing production assistant still transcribes and answers a normal request after any update. Confirm a recognised speaker gets the correct name and an unknown speaker receives a neutral response.
2. Test short and longer phrases from each enrolled speaker. Record the pipeline match and the spoken name; distinguish an unknown match from the wrong person.
3. In the isolated service, deliberately assign a disposable recording to the wrong profile, correct it from History, and confirm the old profile no longer contains that recording. Check that the selected profile's other reference clips remain intact.
4. Undo a corrected assignment and confirm the recording returns to Pending. Confirm cancelled actions do not change data.
5. Open the same History entry in two tabs, correct it in one, then verify that saving the stale entry in the other is rejected.
6. Check speech transcription and speaker identity through the selected bridge and diagnostic agent, and verify simultaneous requests from different devices do not exchange speaker identities.
7. Review the Compose wrapper and the saved backups. Rehearse rollback on the isolated service before changing production. Do not restore an old database over newer recordings or corrections.

Existing user-specific voice profiles, recordings, credentials and database snapshots must remain outside the repository.
