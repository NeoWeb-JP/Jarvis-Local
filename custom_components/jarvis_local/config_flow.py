"""Single-instance UI setup and migration from YAML."""
from homeassistant import config_entries
class JarvisConfigFlow(config_entries.ConfigFlow, domain="jarvis_local"):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("jarvis_local")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Jarvis Local", data={})
        return self.async_show_form(step_id="user")
    async def async_step_import(self, user_input):
        await self.async_set_unique_id("jarvis_local")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Jarvis Local", data={})
