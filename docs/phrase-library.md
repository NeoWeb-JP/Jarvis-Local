# Reusable voice phrases (0.28.0)

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

