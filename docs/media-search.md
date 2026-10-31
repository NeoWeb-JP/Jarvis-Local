# Speech understanding and film/TV search

## What changed in 0.35.0

Declan accepts bounded conversational wrappers such as “Hey Declan, could you
please turn the office light on for me” and “Would you mind turning the lights
off”. It also understands “put the kitchen lights off”, “make the kitchen lights
brighter”, and ordinary current-weather questions. Existing unique-target,
exposure, preview, cancellation and device verification rules still apply.
Unknown device names are not fuzzily executed, and negations are not discarded.

These are transcript/command-understanding improvements, not a replacement STT
model or a measured reduction in microphone word error rate. Existing
inventory-grounded spelling fixes still apply. The conservative leading
lights-off recovery also works when a voice request supplies a satellite ID
without a device ID; negations, corrections and additional commands veto it.
Keep troubleshooting off normally; enable it for a failed request to compare
“Heard” and “Understood”. Real microphone examples are still needed to evaluate
accent, noise, wake-word and STT-engine performance.

## Search only

Examples:

- “Find Desperate Housewives.”
- “Where can I watch Desperate house wives?”
- “Start movie time and play Desperate house wives.”
- “Play the series Desperate Housewives.”
- “Find The Office from 2001.”
- “Preview find Desperate Housewives.”

The compound movie-time example is a **single read-only search** in this phase.
It does not run the movie-time script, play media, turn on a TV/projector, switch
inputs, subscribe, purchase or log in to a streaming account. “Start movie time”
by itself remains the existing household routine. Existing music requests such
as “play country music in kitchen” keep their existing music behavior.

Titles containing “and” remain whole. Split words such as “house wives” compare
equal to “Housewives” during title matching. Fuzzy titles and remakes are
reported as possible/ambiguous matches rather than silently chosen for
availability claims; say “from 2001” or type “(2001)” to disambiguate without
mistaking titles such as Blade Runner 2049 for release years. Quote a title if it
begins with words such as “the show”. A folder/series hit does not confirm that
every episode or season is present.

The sidebar also has **Find films and TV** with a title box and search button.
Typed chat and Assist voice search replies expose the same structured results.

## Search order and limits

1. **Home Assistant media:** filename/folder-name search within the configured
   HA media_dirs (the local “My media” folders/mounts). It reads names,
   not media contents, skips hidden entries and directory symlinks, and does not
   resolve playback URLs. The scan is bounded by time, 300 folders and 5,000
   entries, with up to ten displayed results.
2. **Jellyfin:** reuses the authenticated session of the user's existing
   Home Assistant Jellyfin integration. It searches the libraries visible to
   that session for Movie/Series titles. No second Jellyfin token or guessed
   server address is used. Unloaded/incompatible sessions are reported as
   unavailable. At most three configured servers and two title queries per
   server are considered, with bounded request timeouts.
3. **UK streaming availability:** if no exact local/Jellyfin match was found,
   query TMDB's film/TV catalogue and UK watch-provider data. This requires an
   optional TMDB API read access token. Default selected subscriptions are
   Netflix, Prime Video, Disney+ and Paramount+.

An exact local video match, or a matching folder with a confirmed video inside,
stops the search before external requests. An empty folder or possible
title match does not. Missing configuration, an incomplete scan, authentication
errors, timeouts and provider failures are distinct from an actual no-match
result. Sources not checked are never described as searched. Long or unsupported
compound device requests are rejected before any action.

## Configure UK catalogue search

1. Connect Jellyfin through its normal Home Assistant integration if needed.
   The local/Jellyfin searches work without a TMDB token.
2. Open **Declan settings → Film and TV search**.
3. Select the subscriptions you want compared.
4. Obtain a **TMDB API read access token** from
   [TMDB API settings](https://www.themoviedb.org/settings/api), enter it in the
   password field, and choose **Save media search settings**.
5. A blank token field preserves the saved token. Use **Remove saved token** and
   save to forget it.

The token is stored privately in HA storage under jarvis_local.media_search,
separately from ordinary household settings. The administrator settings API
returns only whether a token is configured, never the token itself. Successful
saves clear the password field and take effect without a restart.
Tokens are sent only as an Authorization header to the fixed TMDB HTTPS API;
redirects are disabled, response size and request durations are bounded, and
provider exceptions/response bodies are not copied into diagnostics or speech.

This version intentionally uses UK/GB availability, as requested. Streaming
results are **catalogue listings**, not a check of paid accounts, entitlements,
subscription tiers or availability of every season. Extra-channel subscriptions
are not treated as included in a direct Prime/Paramount subscription. Rental,
purchase, free/ad-supported and other subscription options are labeled
separately. Check the provider's current offer before paying.

When selected subscriptions have no listing, other returned legal viewing
options are recommended. A UK JustWatch title-search link remains available
when automatic lookup is unconfigured, fails or has no confident match.
Generated search links are navigation aids, not verified availability claims.

## Attribution and references

Availability data: **JustWatch via TMDB**. Provider detail links use the
TMDB URL supplied with the listing, and the sidebar displays attribution.
The search credits section displays the TMDB notice and its official logo.

- [TMDB film/TV search API](https://developer.themoviedb.org/reference/search-multi)
- [TMDB TV watch providers and JustWatch attribution](https://developer.themoviedb.org/reference/tv-series-watch-providers)
- [Home Assistant local media folders](https://www.home-assistant.io/integrations/media_source/)
- [Home Assistant Jellyfin integration](https://www.home-assistant.io/integrations/jellyfin/)
- [Jellyfin client's search method](https://github.com/jellyfin/jellyfin-apiclient-python/blob/master/jellyfin_apiclient_python/api.py)

No television/projector playback implementation or live microphone accuracy
claim is included in this release. Those require separate device configuration
and end-to-end testing.
