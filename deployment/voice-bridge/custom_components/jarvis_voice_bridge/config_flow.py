"""Connection settings for a VoicePipeline test instance."""
import probatio as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from . import DOMAIN
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION=1
    async def async_step_user(self,user_input=None)->FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input['host']}:{user_input['port']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title='Jarvis Voice Bridge',data=user_input)
        return self.async_show_form(step_id='user',data_schema=vol.Schema({vol.Required('host'):str,vol.Required('port',default=10300):vol.All(vol.Coerce(int),vol.Range(min=1,max=65535))}))
