"""Explicit satellite audio targets; never infer players from rooms or devices."""
import logging
import re
from homeassistant.exceptions import HomeAssistantError
_LOGGER = logging.getLogger(__name__)

def is_spoken_stop(text):
    return bool(re.fullmatch(
        r'(?:jarvis[ ,]+)?(?:no[ ,]+)?(?:stop|stop that|be quiet|shut up)[.!? ]*',
        text.strip(), re.I))

async def stop_player(hass, user_input):
    satellite = getattr(user_input, 'satellite_id', None)
    mappings = hass.data.get('jarvis_local', {}).get('settings', {}).get(
        'satellite_media_players', {})
    if not satellite or not isinstance(mappings, dict):
        return
    player = mappings.get(satellite)
    if not isinstance(player, str) or not re.fullmatch(r'media_player\.[a-z0-9_]+', player):
        return
    try:
        await hass.services.async_call(
            'media_player', 'media_stop', {'entity_id': player},
            blocking=True, context=user_input.context)
    except HomeAssistantError:
        _LOGGER.warning('Unable to stop satellite audio for %s', satellite, exc_info=True)
