# Silent satellite stop

“Stop”, “Stop that”, “Be quiet” and “Shut up” (optionally prefixed with
“Jarvis”) stop only the player explicitly configured for the originating
Assist satellite. No acknowledgement is spoken, including when the service
fails. Missing satellite IDs and unmapped satellites run no media action.
Device IDs and room names are never used to guess a player.

The user's successful manual media_stop test confirmed:
`assist_satellite.bedroom_voice_assistant_assist_satellite` →
`media_player.bedroom_voice_assistant`.
Hardware barge-in remains unverified: this code can act only after the
satellite delivers the recognized request to Jarvis.

## Configuration

Open **Jarvis settings → Satellite audio stops**, choose **Add satellite mapping**,
select the Assist satellite and its confirmed media player, then **Save settings**.
Choose each player explicitly; adding a satellite never fills in a player.
Changes are active immediately, without a restart. Removing a row takes effect
only after saving. Each satellite may appear once, with up to 50 mappings.

Saved mappings remain visible as “Missing” if an entity disappears; unchanged
mappings can still be saved, or removed explicitly. New or changed mappings
must select existing entities. The editor does not play audio or test interruption.

The persisted Jarvis settings object supports an optional
`satellite_media_players` dictionary. Example:

```json
{
  "satellite_media_players": {
    "assist_satellite.bedroom_voice_assistant_assist_satellite": "media_player.bedroom_voice_assistant"
  }
}
```

For an installation without saved Jarvis settings, merge this field into
`/config/jarvis_local_settings.json` and restart Home Assistant.
That legacy file is loaded only when there are no persisted settings.
For existing installations, include this field in the existing administrator
settings save request, or use the mapping editor above.
Older sidebar clients that omit the field preserve existing mappings. An empty dictionary clears
the mappings. No household mapping is enabled by default.

Add kitchen and other satellites only after confirming their exact satellite
and player entity IDs. Each value must be one media_player entity ID.

Stop also clears the originating conversation's pending clarification and
lighting follow-up. It bypasses Jarvis's action lock, without cancelling its
running task or unrelated Home Assistant scripts, timers or automations.
Other cancellation phrases retain their existing dialogue behavior.
