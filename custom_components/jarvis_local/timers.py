"""One persistent countdown per Assist satellite."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
import re
from homeassistant.helpers.storage import Store
from homeassistant.components.assist_satellite import AssistSatelliteEntityFeature

_LOGGER=logging.getLogger(__name__)
_NUMBERS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'fifteen':15,'twenty':20,'thirty':30,'forty':40,'forty five':45,'sixty':60,'a':1,'an':1}

def parse(text):
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text.lower().strip().rstrip('.?!'))
    preview=False
    for prefix in ('preview ','dry run ','what would you do if i said '):
        if text.startswith(prefix):preview=True;text=text[len(prefix):];break
    named_status=re.fullmatch(r'(?:how (?:long|much time) (?:is )?left on|status of) (?:the )?([a-z][a-z -]{0,39}) timer',text)
    if named_status:return {'operation':'status','preview':preview,'name':named_status[1]}
    named_cancel=re.fullmatch(r'(?:cancel|stop) (?:the )?([a-z][a-z -]{0,39}) timer',text)
    if named_cancel:return {'operation':'cancel','preview':preview,'name':named_cancel[1]}
    named_set=re.fullmatch(r'set (?:a |the )?([a-z][a-z -]{0,39}) timer for ([a-z\d ]+?) (seconds?|minutes?|hours?)',text)
    if named_set:
        name,raw,unit=named_set.groups();n=int(raw) if raw.isdigit() else _NUMBERS.get(raw)
        if n is None:raise ValueError('Please give the timer duration as a number of minutes, seconds or hours.')
        seconds=n*(3600 if unit.startswith('hour') else 60 if unit.startswith('minute') else 1)
        if not 1<=seconds<=86400:raise ValueError('Please choose a timer between one second and 24 hours.')
        return {'operation':'set','seconds':seconds,'preview':preview,'name':name}
    if text in {'cancel timer','cancel the timer','stop the timer'}:return {'operation':'cancel','preview':preview}
    if text in {'timer status','how long is left on the timer','how much time is left on the timer','how long is left','how long left on the timer'}:return {'operation':'status','preview':preview}
    match=re.fullmatch(r'(?:set (?:a |the )?timer for |(?:a )?)([a-z\d ]+?) (seconds?|minutes?|hours?)(?: timer)?',text)
    if not match:return None
    raw,unit=match.groups();n=int(raw) if raw.isdigit() else _NUMBERS.get(raw)
    if n is None:raise ValueError('Please give the timer duration as a number of minutes, seconds or hours.')
    seconds=n*(3600 if unit.startswith('hour') else 60 if unit.startswith('minute') else 1)
    if not 1<=seconds<=86400:raise ValueError('Please choose a timer between one second and 24 hours.')
    return {'operation':'set','seconds':seconds,'preview':preview}

def describe(seconds):
    seconds=max(0,int(seconds));minutes,sec=divmod(seconds,60);hours,minutes=divmod(minutes,60)
    parts=[f'{n} {unit}'+('s' if n!=1 else '') for n,unit in [(hours,'hour'),(minutes,'minute'),(sec,'second')] if n]
    return ', '.join(parts) or 'less than a second'

class Timers:
    def __init__(self,hass):
        self.hass=hass;self.store=Store(hass,1,'jarvis_local.timers');self.items={};self.tasks={};self.lock=asyncio.Lock()
    async def start(self):
        data=await self.store.async_load()
        if isinstance(data,dict):self.items={k:({'end':v,'name':None} if isinstance(v,str) else v) for k,v in data.items() if isinstance(k,str) and k.startswith('assist_satellite.') and (isinstance(v,str) or (isinstance(v,dict) and isinstance(v.get('end'),str)))}
        for satellite,item in list(self.items.items()):
            try:self._schedule(satellite,item)
            except ValueError:_LOGGER.warning('Ignoring invalid stored timer for %s',satellite);self.items.pop(satellite,None)
    def _schedule(self,satellite,item):
        when=datetime.fromisoformat(item['end'])
        if when.tzinfo is None:raise ValueError('Naive timer deadline')
        self.tasks[satellite]=self.hass.async_create_task(self._wait(satellite,item,when))
    async def _wait(self,satellite,item,when):
        try:
            await asyncio.sleep(max(0,(when-datetime.now(timezone.utc)).total_seconds()))
            async with self.lock:
                if self.items.get(satellite)!=item:return
                self.items.pop(satellite,None);self.tasks.pop(satellite,None)
                await self.store.async_save(self.items)
            try:
                await self.hass.services.async_call('assist_satellite','announce',{'entity_id':satellite,'message':('Your '+item['name']+' timer has finished.' if item.get('name') else 'Your timer has finished.')},blocking=True)
            except Exception:
                _LOGGER.exception('Timer announcement failed for %s',satellite)
                await self.hass.services.async_call('persistent_notification','create',{'title':'Jarvis timer finished','message':'A timer finished, but its satellite announcement failed.'},blocking=True)
        except asyncio.CancelledError:
            return
    async def handle(self,satellite,request):
        if not isinstance(satellite,str) or not satellite.startswith('assist_satellite.'):
            return 'Timers need a voice satellite that supports announcements. Start the timer from that device.'
        state=self.hass.states.get(satellite)
        if state is None or state.state in {'unknown','unavailable'} or not self.hass.services.has_service('assist_satellite','announce'):
            return 'That voice satellite is unavailable for announcements. No timer was started.'
        features=state.attributes.get('supported_features',0)
        if not isinstance(features,int) or not features & int(AssistSatelliteEntityFeature.ANNOUNCE):
            return 'This satellite does not report announcement support. No timer was started.'
        op=request['operation']
        async with self.lock:
            item=self.items.get(satellite)
            end=item['end'] if item else None
            requested_name=request.get('name')
            if op=='set':
                if end:return 'There is already a timer on this device. Cancel it before starting another.'
                length=request['seconds']
                if request['preview']:return 'Preview only. I would start a timer for '+describe(length)+'. No timer was started.'
                end=(datetime.now(timezone.utc)+timedelta(seconds=length)).isoformat()
                item={'end':end,'name':requested_name}
                self.items[satellite]=item
                try:await self.store.async_save(self.items)
                except Exception:self.items.pop(satellite,None);raise
                self._schedule(satellite,item)
                return (requested_name.title()+' timer' if requested_name else 'Timer')+' set for '+describe(length)+'.'
            if not end:return 'There is no active timer on this device.'
            if requested_name and requested_name != item.get('name'):
                return 'There is no '+requested_name+' timer on this device.'
            if op=='status':
                seconds=max(0,round((datetime.fromisoformat(end)-datetime.now(timezone.utc)).total_seconds()))
                return 'There are '+describe(seconds)+' remaining on '+('your '+item['name']+' timer.' if item.get('name') else 'your timer.')
            if request['preview']:return 'Preview only. I would cancel the timer. Nothing was changed.'
            self.items.pop(satellite,None)
            try:await self.store.async_save(self.items)
            except Exception:self.items[satellite]=item;raise
            task=self.tasks.pop(satellite,None)
            if task:task.cancel()
            return 'Timer cancelled.'
    async def stop(self):
        for task in list(self.tasks.values()):task.cancel()
        self.tasks.clear()
