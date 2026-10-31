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
    """Return the routing result; a completed service call does not verify playback."""
    report = {
        'outcome': 'skipped', 'reason': 'missing_satellite',
        'media_player_id': None, 'service_called': False,
    }
    satellite = getattr(user_input, 'satellite_id', None)
    if not satellite:
        return report
    mappings = hass.data.get('jarvis_local', {}).get('settings', {}).get(
        'satellite_media_players', {})
    report['reason'] = 'invalid_mapping'
    if not isinstance(mappings, dict):
        return report
    if satellite not in mappings:
        report['reason'] = 'unmapped_satellite'
        return report
    player = mappings[satellite]
    if not isinstance(player, str) or not re.fullmatch(r'media_player\.[a-z0-9_]+', player):
        return report
    report['media_player_id'] = player
    report['service_called'] = True
    try:
        await hass.services.async_call(
            'media_player', 'media_stop', {'entity_id': player},
            blocking=True, context=user_input.context)
    except (HomeAssistantError, TimeoutError) as err:
        report['outcome'] = 'failed'
        report['reason'] = 'service_timeout' if isinstance(err, TimeoutError) else 'service_error'
        _LOGGER.warning('Unable to stop satellite audio for %s', satellite, exc_info=True)
    else:
        report['outcome'] = 'completed'
        report['reason'] = 'request_sent'
    return report
