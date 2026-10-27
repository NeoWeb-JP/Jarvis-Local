"""Administrator-only panel API. Diagnostics are held in memory only."""
import probatio as vol
from homeassistant.components import websocket_api, conversation
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar
from .settings import save

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/info'})
@callback
def info(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    connection.send_result(msg['id'],{'areas':[{'id':a.id,'name':a.name} for a in ar.async_get(hass).async_list_areas()], 'diagnostics':data.get('diagnostics',[]),'version':'0.12.0','settings':data.get('settings',{})})

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/clear_diagnostics'})
@callback
def clear(hass,connection,msg):
    hass.data.setdefault('jarvis_local',{})['diagnostics']=[]
    connection.send_result(msg['id'],{})

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/process',vol.Required('text'):str,vol.Optional('area_id'):str,vol.Optional('conversation_id'):str})
@websocket_api.async_response
async def process(hass,connection,msg):
    agent=hass.data.get('jarvis_local',{}).get('agent')
    if agent is None:
        connection.send_error(msg['id'],'not_loaded','Jarvis Local is not loaded');return
    area=ar.async_get(hass).async_get_area(msg['area_id']) if msg.get('area_id') else None
    if msg.get('area_id') and area is None:
        connection.send_error(msg['id'],'invalid_area','Selected area no longer exists');return
    user_input=conversation.ConversationInput(text=msg['text'],context=connection.context(msg),conversation_id=msg.get('conversation_id'),device_id=None,satellite_id=None,language='en',agent_id=agent.entity_id)
    result=await agent.async_handle(user_input,area)
    connection.send_result(msg['id'],result.as_dict())

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/save_settings',vol.Required('settings'):dict})
@websocket_api.async_response
async def save_settings(hass,connection,msg):
    try:
        await save(hass,msg['settings'])
    except ValueError as err:
        connection.send_error(msg['id'],'invalid_settings',str(err))
        return
    connection.send_result(msg['id'],{})

def register(hass):
    for handler in [info,clear,process,save_settings]:websocket_api.async_register_command(hass,handler)
