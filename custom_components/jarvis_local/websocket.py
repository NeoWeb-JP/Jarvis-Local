"""Administrator-only panel API. Diagnostics are held in memory only."""
import asyncio
import json
import probatio as vol
from .voice_profiles import public_profiles, validate_profiles, save_profiles_file
from homeassistant.components import websocket_api, conversation
from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers import area_registry as ar
from .settings import save

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/info'})
@callback
def info(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    connection.send_result(msg['id'],{'areas':[{'id':a.id,'name':a.name} for a in ar.async_get(hass).async_list_areas()], 'diagnostics':data.get('diagnostics',[]) if data.get('debug_enabled',False) else [],'debug_enabled':data.get('debug_enabled',False),'version':'0.23.0','settings':data.get('settings',{}),'voice_profiles':public_profiles(data.get('voice_id_config',{}))})

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

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/save_voice_profiles', vol.Required('profiles'):dict})
@websocket_api.async_response
async def save_voice_profiles(hass,connection,msg):
    try:
        profiles=validate_profiles(msg['profiles'])
        data=hass.data.setdefault('jarvis_local',{})
        lock=data.setdefault('voice_profiles_lock',asyncio.Lock())
        async with lock:
            config=await hass.async_add_executor_job(save_profiles_file,hass.config.path('jarvis_voice_id.json'),profiles)
            data['voice_id_config']=config
    except (ValueError, OSError, json.JSONDecodeError) as err:
        connection.send_error(msg['id'],'invalid_profiles',str(err));return
    connection.send_result(msg['id'],{'profiles':public_profiles(config)})

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/set_debug',vol.Required('enabled'):bool})
@websocket_api.async_response
async def set_debug(hass,connection,msg):
    enabled=msg['enabled']
    await Store(hass,1,'jarvis_local.debug').async_save({'enabled':enabled})
    data=hass.data.setdefault('jarvis_local',{})
    data['debug_enabled']=enabled
    if not enabled:data['diagnostics']=[]
    connection.send_result(msg['id'],{'enabled':enabled})

def register(hass):
    for handler in [info,clear,process,save_settings,save_voice_profiles,set_debug]:websocket_api.async_register_command(hass,handler)
