"""Jarvis Local integration and authenticated sidebar chat."""
from pathlib import Path
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import config_validation as cv
DOMAIN = "jarvis_local"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

async def async_setup(hass, config):
    if DOMAIN in config:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={"source":"import"}, data={}))
    return True

async def async_setup_entry(hass, entry):
    data = hass.data.setdefault(DOMAIN, {})
    from .settings import load
    data["settings"] = await load(hass)
    if not data.get('ws_registered'):
        from .websocket import register
        register(hass)
        data['ws_registered']=True
    await hass.config_entries.async_forward_entry_setups(entry, ["conversation"])
    if not data.get("static_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig("/jarvis_local/panel.js", str(Path(__file__).parent / "panel.js"), False)
        ])
        data["static_registered"] = True
    try:
        await panel_custom.async_register_panel(
            hass, frontend_url_path="jarvis-local-app", webcomponent_name="jarvis-local-panel",
            sidebar_title="Jarvis Local", sidebar_icon="mdi:robot",
            module_url="/jarvis_local/panel.js?v=0.9.2",
            config={"agent_id":data["agent"].entity_id}, require_admin=True)
    except Exception:
        await hass.config_entries.async_unload_platforms(entry, ["conversation"])
        raise
    return True

async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, ["conversation"]):
        frontend.async_remove_panel(hass, "jarvis-local-app")
        hass.data[DOMAIN].pop("agent", None)
        hass.data[DOMAIN].pop("diagnostics", None)
        return True
    return False
