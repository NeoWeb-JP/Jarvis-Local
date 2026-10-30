# Reusable voice phrases (0.28.0)

## Interactive sentence builder (0.30.0)

Open **Voice cache → Build a sentence** and tap words or phrases to append them.
The palette contains common linking phrases, music tags, Home Assistant room
names, and reusable recordings from the current voice. Solid buttons indicate a
saved clip in the displayed inventory; dashed buttons may need recording. The
preview checks the exact saved keys, including recordings beyond the displayed
inventory. You can use up to eight clips, move them with the arrow buttons,
remove individual clips, undo the last addition, or clear the sentence.

**Try an example** builds `Playing country music from Spotify in the kitchen.`
without playing it or generating speech. Adjust **Pause between clips** from
0 to 500 milliseconds and select **Preview sentence** to hear one joined audio
file on your current browser/device. Editing the sentence stops playback and
invalidates any preview still loading.

Preview is read-only: it does not call ElevenLabs, save a new recording, execute
the sentence, change the Assist pipeline, or play on household speakers. Only
clips matching the current provider, voice/revision, language and default options
are eligible. If a clip is missing, the entire preview stops and lists it.
**Record clip** fills **Save a new recording** with that clip's text; the separate
**Prepare and save phrase** button is still required to request provider audio.
Changing the pause is only for this audition and does not change automatic
music response timing.

## Import your own recordings (0.29.0)

Open **Voice cache → Import recordings**. Choose your room MP3s (multiple files
at once) or a private Jarvis JSON phrase pack. Review the editable phrase labels,
confirm the recordings use your current Jarvis voice and settings, then select
**Import recordings**. Choosing files only prepares the preview; the import
button sends them to your own Home Assistant. No speech provider is called.

Room labels end in a full stop, such as `master bedroom.`. Filename hyphens and
underscores become spaces; `up-stairs.mp3` becomes `upstairs.`. You can correct
any label before importing. Labels are speech fragments only: they do not rename
Home Assistant areas, create targets, or change device-control behavior.

Imports use the current primary TTS provider, voice, cache revision, English
language and default request options. If voice settings change after you loaded
the cache screen, refresh it before importing. Existing cached clips are kept,
so repeated imports are safe. New recordings appear as `imported_clip` and use
the same keys as generated clips. Music responses can reuse them immediately.

All clips are decoded and validated before new files are saved. Invalid audio,
silent recordings, duplicate labels, changed checksums and insufficient storage
are rejected. Import at most 32 recordings, 2 MiB per recording and 8 MiB of
audio per batch; clips are limited to 30 seconds. Concurrent cache writes or an
unexpected filesystem error can still prevent some saves; the response reports
completed and unsaved recordings so you can retry without replacing saved ones.
Keep private phrase packs out of public GitHub repositories.

Use **Jarvis sidebar → Voice cache** to see saved recordings, preview them on
your browser, prepare reusable clips and save natural whole sentences.
An administrator account is required. Opening the screen, choosing a suggestion,
refreshing and playing a saved recording never call ElevenLabs. **Prepare and
save phrase** requests missing audio through your existing primary TTS entity;
this can consume provider credits. No additional API key is stored by Jarvis.

The Assist pipeline must use **Jarvis Voice Manager** as its text-to-speech
engine. Choosing ElevenLabs directly bypasses this library. The screen shows
the manager's entity ID and whether persistent caching and phrase assembly are
enabled. Integration options include `phrase_library_enabled`; turn it off to
use only normal whole-sentence synthesis and caching.

## What gets reused

An existing exact whole-sentence recording is preferred. Otherwise the following
complete English response shapes can be assembled from clips:

- `Playing {genre} music from Spotify in the {room}.`
- `I requested {music} in {room}.` (the current music command response)
- `I’ve requested {genre} music from Spotify in the {room}.`

The actual command response is preserved. Assembly never changes a request into
a claim that playback has been verified. Other replies—including unknown text,
weather, errors, corrections and compound sentences—use normal whole-sentence
TTS. No household action runs when preparing or previewing a phrase.

For the first shape, clips are `Playing`, the genre, `music from Spotify in the`,
and the room followed by a full stop, for example `kitchen.`. For the current
request response they are `I requested`, the music, `in`, and `kitchen.`.
Room suggestions come from Home Assistant areas. Suggestions fill the phrase
box; prepare them individually when wanted. Clip identity ignores capitalization,
but retains punctuation, voice, provider, cache revision, language and options.
Preparing `Kitchen.` also supplies `kitchen.`. A room ending a sentence is a
different clip from the same name in the middle of a sentence.

New combinations generate missing clips sequentially and reuse saved ones.
Concurrent identical clips coalesce into one provider request. If the genre
changes from country to jazz in the same room, only `jazz` is requested. The
result is cached too, so repeating that sentence requires no joining or generation.

FFmpeg decodes each new clip into mono 24 kHz, 16-bit PCM WAV once. Boundary
silence is shortened conservatively and clips are joined into **one** WAV for
the normal HA playback path. Compressed MP3 bytes are never directly joined.
Speech melody can still sound less natural than a whole sentence. Prepare a
whole sentence with its exact wording when you prefer a natural recording;
it takes precedence over an assembled recording. Changing voice/provider settings
requires a new `cache_revision` in Jarvis integration options when those settings
are not passed explicitly in the synthesis request.

If decoding/joining fails, Jarvis requests the original whole sentence. If the
primary speech provider fails, the existing fallback policy handles the whole
original response. It never fills one missing fragment with another voice.

## Storage and visibility

All audio remains under `/config/jarvis_voice_cache`, outside the integration's
update directory. Existing recordings remain compatible. New recordings have
private JSON sidecars with their text, provider, voice identity, kind and creation
time. Older files without sidecars are listed as older recordings with unknown
text. No credentials or full synthesis-option dictionaries are saved in sidecars.
The screen lists the newest 200 entries and reports the total count and disk usage.
These files contain household speech; keep them out of public repositories.

The shared cache has a **256 MiB ceiling** and leaves **512 MiB free** on HA's
filesystem. Once either threshold is reached, existing recordings stay intact
and new audio is served without saving. No automatic eviction discards clips
that may have cost credits. Explicit preparation is blocked when storage is
already full; concurrent writes can still exhaust the budget during generation.
The screen shows skipped writes. The limit includes audio and sidecars; it does
not limit HA's separate built-in TTS cache, backups or other app data. Existing
files above the limit are preserved and additional writes stop.

Counters show requests handled by Voice Manager since startup, not your billed
ElevenLabs usage. HA can serve an outer TTS cache hit without calling the manager,
and the primary TTS entity may have its own cache. Use ElevenLabs usage/history
to confirm billing savings. Cached audio playback from the screen makes no
synthesis request. There is no publicly served cache directory: preview audio is
returned only over the administrator-authenticated WebSocket connection.

## Validation and rollout

Tests cover exact templates, changing genres/rooms, restart persistence,
concurrent requests, voice/settings isolation, failure recovery, budget and
free-space checks, audio ordering, manager routing and panel interactions.
CI installs FFmpeg and tests MP3 decoding too. Local Windows execution uses
controlled HA providers and a timer/executor-only runner because this host's
network socket initialization stalls before asyncio tests start.

Main has been updated without a PR, following the owner's preference. No live
HA deployment, restart, pipeline change, paid pre-generation or Proxmox storage
change is part of this implementation. After deployment, test one phrase in the
screen, listen to its preview, then test the manager in your Assist pipeline.





