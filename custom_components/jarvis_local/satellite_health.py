"""Read-only checks of saved satellite audio mappings."""
import re


def _status(hass, entity_id, domain):
    if not isinstance(entity_id, str) or not re.fullmatch(domain + r'\.[a-z0-9_]+', entity_id):
        return 'invalid'
    state = hass.states.get(entity_id)
    if state is None:
        return 'missing'
    if state.state in {'unavailable', 'unknown'}:
        return state.state
    return 'available'


def check_mappings(hass):
    mappings = hass.data.get('jarvis_local', {}).get('settings', {}).get('satellite_media_players', {})
    if not isinstance(mappings, dict) or len(mappings) > 50:
        return {'mappings': [], 'error': 'Saved satellite mappings are invalid. Review and save the settings.'}
    counts = {}
    for player in mappings.values():
        if isinstance(player, str):
            counts[player] = counts.get(player, 0) + 1
    results = []
    for satellite, player in mappings.items():
        source_status = _status(hass, satellite, 'assist_satellite')
        player_status = _status(hass, player, 'media_player')
        results.append({
            'satellite_id': satellite if isinstance(satellite, str) else None,
            'media_player_id': player if isinstance(player, str) else None,
            'satellite_status': source_status, 'player_status': player_status,
            'entities_available': source_status == player_status == 'available',
            'shared_player': isinstance(player, str) and counts[player] > 1,
        })
    return {'mappings': results, 'error': None}
