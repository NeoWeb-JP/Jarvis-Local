"""Administrator-only panel API. Diagnostics are held in memory only."""
import asyncio
import json
import base64
import wave
import probatio as vol
from .voice_profiles import public_profiles, validate_profiles, save_profiles_file
from homeassistant.components import websocket_api, conversation
from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers import area_registry as ar
from .settings import save
from .satellite_health import check_mappings
from .media_search_config import public_config as public_media_search, save as save_media_search_config
from .media_search import parse_search
from .media_search_adapters import search as run_media_search
from homeassistant.exceptions import HomeAssistantError


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/voice_cache',
                                vol.Optional('query',default=''):str,vol.Optional('page',default=1):int})
@websocket_api.async_response
async def voice_cache(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    cache=data.get('voice_cache')
    manager=data.get('voice_manager')
    if cache is None or manager is None:
        connection.send_error(msg['id'],'not_loaded','Jarvis Voice Manager is not loaded');return
    try:
        result=await cache.snapshot(query=msg.get('query',''),page=msg.get('page',1),page_size=10)
    except ValueError as err:
        connection.send_error(msg['id'],'invalid_search',str(err));return
    except OSError:
        connection.send_error(msg['id'],'storage_error','Could not read voice cache storage');return
    result['usage']=data['voice_usage'].snapshot()
    result['directory']=str(cache.directory)
    result['entity_id']=manager.entity_id
    result['enabled']=manager._entry.options.get('cache_enabled',True)
    result['phrases_enabled']=manager._entry.options.get('phrase_library_enabled',True)
    result['import_voice_token']=manager.import_token()
    identity=manager.import_identity()
    result['builder_voice']={key:identity[key] for key in ('provider','voice_id')}
    result['rooms']=[a.name for a in ar.async_get(hass).async_list_areas()]
    connection.send_result(msg['id'],result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/save_voice_sentence',
    vol.Required('parts'):list,vol.Required('voice_token'):str,vol.Optional('gap_ms',default=20):int})
@websocket_api.async_response
async def save_voice_sentence(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    manager=data.get('voice_manager')
    if manager is None:
        connection.send_error(msg['id'],'not_loaded','Voice Manager is not loaded');return
    lock=data.setdefault('phrase_generation_lock',asyncio.Lock())
    if lock.locked():
        connection.send_error(msg['id'],'busy','Another phrase operation is running');return
    try:
        async with lock:
            result=await manager.save_sentence(msg['parts'],msg['voice_token'],msg.get('gap_ms',20))
    except (HomeAssistantError,ValueError,OSError,EOFError,wave.Error,TimeoutError) as err:
        connection.send_error(msg['id'],'save_failed',str(err) if isinstance(err,ValueError)
            else 'Could not save the complete sentence. Completed clips are kept; retry to reuse them.');return
    connection.send_result(msg['id'],result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/preview_voice_sentence',
    vol.Required('parts'):list,vol.Required('voice_token'):str,vol.Optional('gap_ms',default=20):int})
@websocket_api.async_response
async def preview_voice_sentence(hass,connection,msg):
    manager=hass.data.get('jarvis_local',{}).get('voice_manager')
    if manager is None:
        connection.send_error(msg['id'],'not_loaded','Jarvis Voice Manager is not loaded');return
    try:
        result=await manager.preview_sentence(msg['parts'],msg['voice_token'],msg.get('gap_ms',20))
        if 'audio' in result:result['audio']=base64.b64encode(result['audio']).decode('ascii')
    except (ValueError,OSError,EOFError,wave.Error) as err:
        connection.send_error(msg['id'],'preview_failed',str(err) if isinstance(err,ValueError)
                              else 'A saved clip could not be read; import it again');return
    connection.send_result(msg['id'],result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/import_voice_clips',
    vol.Required('clips'):list,vol.Required('voice_token'):str})
@websocket_api.async_response
async def import_voice_clips(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    manager=data.get('voice_manager')
    if manager is None:
        connection.send_error(msg['id'],'not_loaded','Jarvis Voice Manager is not loaded');return
    lock=data.setdefault('phrase_generation_lock',asyncio.Lock())
    if lock.locked():
        connection.send_error(msg['id'],'busy','Another phrase operation is running');return
    try:
        async with lock:
            result=await manager.import_clips(msg['clips'],msg['voice_token'])
    except (HomeAssistantError,ValueError,OSError,TimeoutError,EOFError) as err:
        connection.send_error(msg['id'],'import_failed',str(err) if isinstance(err,ValueError)
                              else 'Could not import audio; check Home Assistant logs');return
    connection.send_result(msg['id'],result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/voice_cache_audio',
    vol.Required('key'):str,vol.Required('extension'):str})
@websocket_api.async_response
async def voice_cache_audio(hass,connection,msg):
    cache=hass.data.get('jarvis_local',{}).get('voice_cache')
    if cache is None:
        connection.send_error(msg['id'],'not_loaded','Voice cache is not loaded');return
    try:
        audio=await cache.saved_audio(msg['key'],msg['extension'])
    except (OSError,ValueError):
        connection.send_error(msg['id'],'invalid_audio','That recording is not available');return
    connection.send_result(msg['id'],{'audio':base64.b64encode(audio).decode('ascii'),
                                    'extension':msg['extension']})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/prepare_voice_phrase',
    vol.Required('text'):str,vol.Required('kind'):vol.In(['clip','sentence'])})
@websocket_api.async_response
async def prepare_voice_phrase(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    manager=data.get('voice_manager')
    if manager is None:
        connection.send_error(msg['id'],'not_loaded','Jarvis Voice Manager is not loaded');return
    # Serialize explicit admin generation and reject clicks queued by another client.
    lock=data.setdefault('phrase_generation_lock',asyncio.Lock())
    if lock.locked():
        connection.send_error(msg['id'],'busy','A phrase is already being prepared');return
    try:
        async with lock:
            result=await manager.prepare_phrase(msg['text'],msg['kind'])
    except (HomeAssistantError,ValueError,OSError,TimeoutError) as err:
        connection.send_error(msg['id'],'generation_failed',
                              str(err) if isinstance(err,ValueError) else 'Speech generation failed; check Home Assistant logs');return
    connection.send_result(msg['id'],result)

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/info'})
@callback
def info(hass,connection,msg):
    data=hass.data.get('jarvis_local',{})
    connection.send_result(msg['id'],{'areas':[{'id':a.id,'name':a.name} for a in ar.async_get(hass).async_list_areas()], 'diagnostics':data.get('diagnostics',[]) if data.get('debug_enabled',False) else [],'debug_enabled':data.get('debug_enabled',False),'version':data.get('version'),'settings':data.get('settings',{}),'voice_profiles':public_profiles(data.get('voice_id_config',{})),'media_search_config':public_media_search(hass)})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/save_media_search',vol.Required('config'):dict})
@websocket_api.async_response
async def save_media_search(hass,connection,msg):
    try:
        result=await save_media_search_config(hass,msg['config'])
    except ValueError as err:
        connection.send_error(msg['id'],'invalid_settings',str(err));return
    except (OSError,HomeAssistantError):
        connection.send_error(msg['id'],'save_failed','Could not save media search settings.');return
    connection.send_result(msg['id'],result)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/search_media',vol.Required('query'):str})
@websocket_api.async_response
async def search_media(hass,connection,msg):
    data=hass.data.setdefault('jarvis_local',{})
    if data.get('media_search_busy'):
        connection.send_error(msg['id'],'busy','A media search is already running.');return
    try:
        query=msg['query'].strip()
        if not query or len(query)>200:
            raise ValueError('Enter a film or TV title of up to 200 characters.')
        request=parse_search('find '+query)
        if request is None:
            raise ValueError('Enter a film or TV title.')
        data['media_search_busy']=True
        result=await run_media_search(hass,request)
    except ValueError as err:
        connection.send_error(msg['id'],'invalid_search',str(err));return
    except (OSError,HomeAssistantError,TimeoutError):
        connection.send_error(msg['id'],'search_failed','Could not complete the media search.');return
    finally:
        data['media_search_busy']=False
    connection.send_result(msg['id'],result)

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/check_satellite_mappings'})
@callback
def check_satellite_mappings(hass,connection,msg):
    connection.send_result(msg['id'],check_mappings(hass))

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

@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required('type'):'jarvis_local/check_voice_bridge'})
@websocket_api.async_response
async def check_voice_bridge(hass,connection,msg):
    entries=hass.config_entries.async_entries('jarvis_voice_bridge')
    results=[]
    for entry in entries:
        host=entry.data.get('host');port=entry.data.get('port')
        if not isinstance(host,str) or not isinstance(port,int) or not 1<=port<=65535:
            results.append({'name':entry.title,'reachable':False,'reason':'Invalid bridge configuration'});continue
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_connection(host,port),timeout=3)
            writer.close()
            await writer.wait_closed()
            results.append({'name':entry.title,'reachable':True})
        except (OSError,TimeoutError):
            results.append({'name':entry.title,'reachable':False,'reason':'TCP connection failed'})
    connection.send_result(msg['id'],{'bridges':results})

def register(hass):
    for handler in [info,clear,process,check_satellite_mappings,save_settings,save_voice_profiles,set_debug,check_voice_bridge,
                    save_media_search,search_media,
                    voice_cache,voice_cache_audio,prepare_voice_phrase,import_voice_clips,
                    preview_voice_sentence,save_voice_sentence]:websocket_api.async_register_command(hass,handler)
