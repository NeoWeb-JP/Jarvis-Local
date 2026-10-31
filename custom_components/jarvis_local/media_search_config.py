"""Private search configuration; provider tokens never leave the backend."""
import re
from .media_search import SUBSCRIPTIONS

KEY = "jarvis_local.media_search"
DEFAULTS = {"region": "GB", "subscriptions": list(SUBSCRIPTIONS), "tmdb_token": ""}


def current(hass):
    return hass.data.get("jarvis_local", {}).get("media_search_config", DEFAULTS)


def public_config(hass):
    config = current(hass)
    return {"region": config.get("region", "GB"),
            "subscriptions": config.get("subscriptions", list(SUBSCRIPTIONS)),
            "catalogue_configured": bool(config.get("tmdb_token"))}


def validate(data, previous=None):
    if not isinstance(data, dict) or set(data) - {"region", "subscriptions", "tmdb_token", "clear_token"}:
        raise ValueError("Invalid media search settings")
    previous = previous or DEFAULTS
    region = data.get("region", previous.get("region", "GB"))
    if region != "GB":
        raise ValueError("This version supports United Kingdom availability (GB)")
    subscriptions = data.get("subscriptions", previous.get("subscriptions", list(SUBSCRIPTIONS)))
    if (not isinstance(subscriptions, list) or len(subscriptions) > len(SUBSCRIPTIONS)
            or any(not isinstance(item, str) or item not in SUBSCRIPTIONS for item in subscriptions)
            or len(set(subscriptions)) != len(subscriptions)):
        raise ValueError("Choose subscription services from the supported list")
    token = data.get("tmdb_token", "")
    if not isinstance(token, str) or (token and not re.fullmatch(r"[A-Za-z0-9._-]{20,2048}", token)):
        raise ValueError("Enter a TMDB API read access token")
    clear = data.get("clear_token", False)
    if not isinstance(clear, bool) or (clear and token):
        raise ValueError("Choose either a new token or Remove saved token")
    return {"region": region, "subscriptions": list(subscriptions),
            "tmdb_token": "" if clear else token or previous.get("tmdb_token", "")}


async def load(hass):
    from homeassistant.helpers.storage import Store
    saved = await Store(hass, 1, KEY).async_load()
    return validate(saved or {}, DEFAULTS)


async def save(hass, data):
    from homeassistant.helpers.storage import Store
    config = validate(data, current(hass))
    await Store(hass, 1, KEY).async_save(config)
    hass.data.setdefault("jarvis_local", {})["media_search_config"] = config
    return public_config(hass)
