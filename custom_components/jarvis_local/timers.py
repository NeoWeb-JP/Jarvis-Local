"""Persistent named timers scoped to one Assist satellite."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import logging
import re
from uuid import uuid4
from homeassistant.helpers.storage import Store
from homeassistant.components.assist_satellite import AssistSatelliteEntityFeature

_LOGGER=logging.getLogger(__name__)
_NUMBERS={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,'fifteen':15,'twenty':20,'thirty':30,'forty':40,'forty five':45,'sixty':60,'a':1,'an':1}

def duration(raw, unit):
    n=int(raw) if raw.isdigit() else _NUMBERS.get(raw)
    if n is None:raise ValueError('Please give the timer duration as a number of minutes, seconds or hours.')
    seconds=n*(3600 if unit.startswith('hour') else 60 if unit.startswith('minute') else 1)
    if not 1<=seconds<=86400:raise ValueError('Please choose a duration between one second and 24 hours.')
    return seconds

def parse(text):
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text.lower().strip().rstrip('.?!'))
    preview=False
    for prefix in ('preview ','dry run ','what would you do if i said '):
        if text.startswith(prefix):preview=True;text=text[len(prefix):];break
    if re.fullmatch(r'(?:cancel|stop) (?:all |my |all my |the )?timers',text):return {'operation':'cancel_all','preview':preview}
    m=re.fullmatch(r'(add|remove|subtract) ([a-z\d -]+?) (seconds?|minutes?|hours?) (?:to|from) (?:the |my )?(?:([a-z][a-z -]{0,39}) )?timer',text)
    if m:
        op,raw,unit,name=m.groups()
        if (op=='add' and ' from ' in text) or (op!='add' and ' to ' in text):raise ValueError('Please say add time to a timer or remove time from it.')
        return {'operation':'adjust','seconds':duration(raw.replace('-',' '),unit)*(1 if op=='add' else -1),'name':name,'preview':preview}
    m=re.fullmatch(r'(?:how (?:long|much time) (?:is )?left on|status of) (?:the |my )?([a-z][a-z -]{0,39}) timer',text)
    if m and m[1] not in {'the','my'}:return {'operation':'status','preview':preview,'name':m[1]}
    m=re.fullmatch(r'(?:cancel|stop) (?:the |my )?([a-z][a-z -]{0,39}) timer',text)
    if m and m[1] not in {'the','my'}:return {'operation':'cancel','preview':preview,'name':m[1]}
    m=re.fullmatch(r'(?:set|create|start) (?:a |the |my )?([a-z][a-z -]{0,39}) timer for ([a-z\d -]+?) (seconds?|minutes?|hours?)',text)
    if m and m[1] not in {'a','the','my'}:return {'operation':'set','seconds':duration(m[2].replace('-',' '),m[3]),'preview':preview,'name':m[1]}
    if text in {'cancel timer','cancel the timer','cancel my timer','stop the timer'}:return {'operation':'cancel','preview':preview}
    if text in {'timer status','how long is left on the timer','how much time is left on the timer','how long is left','how long left on the timer'}:return {'operation':'status','preview':preview}
    m=re.fullmatch(r'(?:(?:set|create|start) (?:a |the |my )?timer for |(?:a )?)([a-z\d -]+?) (seconds?|minutes?|hours?)(?: timer)?',text)
    if m:return {'operation':'set','seconds':duration(m[1].replace('-',' '),m[2]),'preview':preview}
    return None

def describe(seconds):
    seconds=max(0,int(seconds));minutes,sec=divmod(seconds,60);hours,minutes=divmod(minutes,60)
    parts=[f'{n} {unit}'+('s' if n!=1 else '') for n,unit in [(hours,'hour'),(minutes,'minute'),(sec,'second')] if n]
    return ', '.join(parts) or 'less than a second'

class Timers:
    def __init__(self,hass):
        self.hass=hass;self.store=Store(hass,1,'jarvis_local.timers');self.items={};self.tasks={};self.lock=asyncio.Lock()
    async def start(self):
        data=await self.store.async_load()
        if isinstance(data,dict):
            for satellite,value in data.items():
                if not isinstance(satellite,str) or not satellite.startswith('assist_satellite.'):continue
                if isinstance(value,str):value={'end':value,'name':None}
                if isinstance(value,dict) and isinstance(value.get('end'),str):value={value.get('name') or '':value}
                if not isinstance(value,dict):continue
                for name,item in value.items():
                    if not isinstance(name,str) or not isinstance(item,dict) or not isinstance(item.get('end'),str):continue
                    try:
                        when=datetime.fromisoformat(item['end'])
                        if when.tzinfo is None:raise ValueError('Naive deadline')
                    except (ValueError,TypeError):
                        _LOGGER.warning('Ignoring invalid stored timer on %s',satellite);continue
                    item={'end':item['end'],'name':name or None,'id':item.get('id') or uuid4().hex}
                    self.items.setdefault(satellite,{})[name]=item;self._schedule(satellite,name,item)
    def _schedule(self,satellite,name,item):
        self.tasks[(satellite,name)]=self.hass.async_create_task(self._wait(satellite,name,item))
    async def _wait(self,satellite,name,item):
        try:
            when=datetime.fromisoformat(item['end'])
            await asyncio.sleep(max(0,(when-datetime.now(timezone.utc)).total_seconds()))
            async with self.lock:
                if self.items.get(satellite,{}).get(name)!=item:return
                before=deepcopy(self.items)
                self.items[satellite].pop(name)
                if not self.items[satellite]:self.items.pop(satellite)
                try:await self.store.async_save(self.items)
                except Exception:
                    self.items=before
                    _LOGGER.exception('Could not persist completed timer; retaining it for recovery')
                    return
                self.tasks.pop((satellite,name),None)
            try:
                await self.hass.services.async_call('assist_satellite','announce',{'entity_id':satellite,'message':('Your '+name+' timer has finished.' if name else 'Your timer has finished.')},blocking=True)
            except Exception:
                _LOGGER.exception('Timer announcement failed for %s',satellite)
                await self.hass.services.async_call('persistent_notification','create',{'title':'Jarvis timer finished','message':'A timer finished, but its satellite announcement failed.'},blocking=True)
        except asyncio.CancelledError:return
    async def handle(self,satellite,request):
        if not isinstance(satellite,str) or not satellite.startswith('assist_satellite.'):
            return 'Timers need a voice satellite that supports announcements. Start the timer from that device.'
        state=self.hass.states.get(satellite)
        if state is None or state.state in {'unknown','unavailable'} or not self.hass.services.has_service('assist_satellite','announce'):
            return 'That voice satellite is unavailable for announcements. No timer was changed.'
        features=state.attributes.get('supported_features',0)
        if not isinstance(features,int) or not features & int(AssistSatelliteEntityFeature.ANNOUNCE):
            return 'This satellite does not report announcement support. No timer was changed.'
        op=request['operation'];requested=request.get('name');preview=request.get('preview',False)
        async with self.lock:
            timers=self.items.get(satellite,{})
            if op=='set':
                key=requested or ''
                if key in timers:return 'A '+(key+' ' if key else '')+'timer already exists on this device.'
                if len(timers)>=20:return 'This device already has 20 timers. Please cancel one first.'
                if preview:return 'Preview only. I would start '+(key+' ' if key else 'a ')+'timer for '+describe(request['seconds'])+'. No timer was started.'
                item={'end':(datetime.now(timezone.utc)+timedelta(seconds=request['seconds'])).isoformat(),'name':key or None,'id':uuid4().hex}
                before=deepcopy(self.items);self.items.setdefault(satellite,{})[key]=item
                try:await self.store.async_save(self.items)
                except Exception:self.items=before;raise
                self._schedule(satellite,key,item)
                return (key.title()+' timer' if key else 'Timer')+' set for '+describe(request['seconds'])+'.'
            if not timers:return 'There is no active timer on this device.'
            if op=='cancel_all':
                if preview:return 'Preview only. I would cancel all timers on this device. Nothing was changed.'
                before=deepcopy(self.items);self.items.pop(satellite)
                try:await self.store.async_save(self.items)
                except Exception:self.items=before;raise
                for key in timers:
                    task=self.tasks.pop((satellite,key),None)
                    if task:task.cancel()
                return 'All timers on this device cancelled.'
            if requested is not None:
                if requested not in timers:return 'There is no '+requested+' timer on this device.'
                key=requested
            elif len(timers)==1:key=next(iter(timers))
            else:return 'There are multiple timers on this device. Please name the timer.'
            item=timers[key];label=('the '+key+' timer' if key else 'the timer')
            if op=='status':
                seconds=max(0,round((datetime.fromisoformat(item['end'])-datetime.now(timezone.utc)).total_seconds()))
                return 'There are '+describe(seconds)+' remaining on '+label+'.'
            if op=='adjust':
                delta=request['seconds'];new_end=datetime.fromisoformat(item['end'])+timedelta(seconds=delta)
                if new_end-datetime.now(timezone.utc)>timedelta(days=1):return 'A timer cannot exceed 24 hours. Nothing was changed.'
                if preview:return 'Preview only. I would '+('add '+describe(delta)+' to ' if delta>0 else 'remove '+describe(-delta)+' from ')+label+'. Nothing was changed.'
                updated={**item,'end':new_end.isoformat(),'id':uuid4().hex};before=deepcopy(self.items);self.items[satellite][key]=updated
                try:await self.store.async_save(self.items)
                except Exception:self.items=before;raise
                task=self.tasks.pop((satellite,key),None)
                if task:task.cancel()
                self._schedule(satellite,key,updated)
                return ('Added '+describe(delta)+' to ' if delta>0 else 'Removed '+describe(-delta)+' from ')+label+'.'
            if op!='cancel':return 'I could not understand that timer request. Nothing was changed.'
            if preview:return 'Preview only. I would cancel '+label+'. Nothing was changed.'
            before=deepcopy(self.items);self.items[satellite].pop(key)
            if not self.items[satellite]:self.items.pop(satellite)
            try:await self.store.async_save(self.items)
            except Exception:self.items=before;raise
            task=self.tasks.pop((satellite,key),None)
            if task:task.cancel()
            return label.capitalize()+' cancelled.'
    async def stop(self):
        for task in list(self.tasks.values()):task.cancel()
        self.tasks.clear()
