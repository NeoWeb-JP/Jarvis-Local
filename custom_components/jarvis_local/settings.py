"""Household settings stored outside the integration directory."""
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def _read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("settings must be a JSON object")
        return data
    except FileNotFoundError:
        return {}

async def load(hass):
    try:
        return await hass.async_add_executor_job(_read, hass.config.path("jarvis_local_settings.json"))
    except (OSError, ValueError) as err:
        _LOGGER.error("Invalid Jarvis settings: %s", err)
        raise

def get(hass, key, default=None):
    return hass.data.get("jarvis_local", {}).get("settings", {}).get(key, default)
