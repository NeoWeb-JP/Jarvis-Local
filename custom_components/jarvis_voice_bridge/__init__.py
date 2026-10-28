"""Experimental per-request speaker bridge."""
from homeassistant.helpers import config_validation as cv
DOMAIN='jarvis_voice_bridge'
CONFIG_SCHEMA=cv.empty_config_schema(DOMAIN)
async def async_setup_entry(hass,entry):
    await hass.config_entries.async_forward_entry_setups(entry,['stt','conversation'])
    return True
async def async_unload_entry(hass,entry):
    return await hass.config_entries.async_unload_platforms(entry,['stt','conversation'])
