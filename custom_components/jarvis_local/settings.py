"""Private settings, persisted in Home Assistant storage."""
import json
import logging
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)
KEY = 'jarvis_local.settings'
FIELDS = {'weather':'weather', 'thermostat':'climate', 'car_cable_sensor':'binary_sensor', 'car_battery_sensor':'sensor', 'guest_mode':'input_boolean', 'guest_names':'input_text', 'music_script':'script', 'personality_script':'script', 'phonetic_script':'script'}

def _read_legacy(path):
    try:
        with open(path, encoding='utf-8') as stream:
            data=json.load(stream)
        if not isinstance(data, dict):
            raise ValueError('settings must be an object')
        return data
    except FileNotFoundError:
        return {}

async def load(hass):
    store=Store(hass, 1, KEY)
    data=await store.async_load()
    if data is None:
        data=await hass.async_add_executor_job(_read_legacy, hass.config.path('jarvis_local_settings.json'))
    if not isinstance(data, dict):
        raise ValueError('Jarvis settings must be an object')
    return data

async def save(hass, data):
    if not isinstance(data, dict) or set(data)-set(FIELDS)-{'switch_lights', 'satellite_media_players'}:
        raise ValueError('Invalid settings fields')
    cleaned={}
    for key, domain in FIELDS.items():
        value=data.get(key, '')
        if not isinstance(value, str):
            raise ValueError('Invalid '+key)
        if value:
            if not value.startswith(domain+'.') or hass.states.get(value) is None:
                raise ValueError('Choose an existing '+domain+' entity for '+key)
            cleaned[key]=value
    mappings=data.get('switch_lights', {})
    if not isinstance(mappings, dict) or len(mappings)>50:
        raise ValueError('Invalid switch mappings')
    switches={}
    for name, entity in mappings.items():
        if not isinstance(name,str) or not name.strip() or len(name)>100 or not isinstance(entity,str) or not entity.startswith('switch.') or hass.states.get(entity) is None:
            raise ValueError('Each switch needs a name and an existing switch entity')
        name=' '.join(name.lower().split())
        if name in switches:raise ValueError('Switch names must be unique')
        switches[name]=entity
    cleaned['switch_lights']=switches
    # Older sidebar clients omit this field; preserve their existing mappings.
    players=data.get('satellite_media_players',
        hass.data.get('jarvis_local', {}).get('settings', {}).get('satellite_media_players', {}))
    if not isinstance(players, dict) or len(players)>50:
        raise ValueError('Invalid satellite media player mappings')
    import re
    for satellite, player in players.items():
        if (not isinstance(satellite, str) or not re.fullmatch(r'assist_satellite\.[a-z0-9_]+', satellite)
                or not isinstance(player, str) or not re.fullmatch(r'media_player\.[a-z0-9_]+', player)):
            raise ValueError('Each satellite needs an explicit media_player entity')
    cleaned['satellite_media_players']=dict(players)
    await Store(hass, 1, KEY).async_save(cleaned)
    hass.data['jarvis_local']['settings']=cleaned

def get(hass, key, default=None):
    value=hass.data.get('jarvis_local', {}).get('settings', {}).get(key, default)
    if not value and key == 'thermostat':
        candidates=hass.states.async_all('climate')
        if len(candidates)==1:
            return candidates[0].entity_id
    return value
