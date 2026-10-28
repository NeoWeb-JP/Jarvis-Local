import asyncio
import types
import unittest
from datetime import datetime,timedelta,timezone
import test_agent_dialogue
from jarvis_test import timers
class Store:
    data=None
    def __init__(self,*args):pass
    async def async_load(self):return None if Store.data is None else Store.data.copy()
    async def async_save(self,data):Store.data=data.copy()
class Services:
    def __init__(self):self.calls=[]
    def has_service(self,*args):return True
    async def async_call(self,*args,**kwargs):self.calls.append((args,kwargs))
class Hass:
    def __init__(self):
        self.services=Services()
        self.states=types.SimpleNamespace(get=lambda key:types.SimpleNamespace(state='idle',attributes={'supported_features':1}))
    def async_create_task(self,coro):return asyncio.create_task(coro)
class TimerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Store.data=None;timers.Store=Store;self.hass=Hass();self.t=timers.Timers(self.hass);await self.t.start()
    async def asyncTearDown(self):await self.t.stop();await asyncio.sleep(0)
    def test_parse(self):
        self.assertEqual(timers.parse('set a timer for ten minutes')['seconds'],600)
        self.assertEqual(timers.parse('preview cancel timer')['operation'],'cancel')
        with self.assertRaises(ValueError):timers.parse('set a timer for 99 hours')
    async def test_set_preview_status_cancel_and_isolation(self):
        a='assist_satellite.kitchen';b='assist_satellite.bedroom'
        await self.t.handle(a,timers.parse('preview set a timer for ten minutes'))
        self.assertEqual(self.t.items,{})
        await self.t.handle(a,timers.parse('set a timer for ten minutes'))
        self.assertIn('remaining',await self.t.handle(a,timers.parse('timer status')))
        self.assertIn('no active timer',(await self.t.handle(b,timers.parse('timer status'))).lower())
        self.assertIn('already',await self.t.handle(a,timers.parse('set a timer for five minutes')))
        await self.t.handle(a,timers.parse('cancel timer'));self.assertEqual(Store.data,{})
    async def test_named_timer_status_cancel_and_restore(self):
        satellite='assist_satellite.kitchen'
        self.assertEqual(timers.parse('set a pasta timer for ten minutes')['name'],'pasta')
        await self.t.handle(satellite,timers.parse('set a pasta timer for ten minutes'))
        self.assertIn('pasta timer',await self.t.handle(satellite,timers.parse('how long is left on the pasta timer')))
        self.assertIn('no rice timer', (await self.t.handle(satellite,timers.parse('cancel the rice timer'))).lower())
        self.assertIn(satellite,self.t.items)
        await self.t.stop();self.t=timers.Timers(self.hass);await self.t.start()
        self.assertEqual(self.t.items[satellite]['pasta']['name'],'pasta')
        await self.t.handle(satellite,timers.parse('cancel the pasta timer'))
        self.assertEqual(self.t.items,{})
    async def test_multiple_adjust_cancel_and_isolation(self):
        a='assist_satellite.kitchen';b='assist_satellite.bedroom'
        self.assertEqual(timers.parse('create a pasta timer for 20 minutes')['seconds'],1200)
        await self.t.handle(a,timers.parse('create a pasta timer for 20 minutes'))
        await self.t.handle(a,timers.parse('set a tea timer for five minutes'))
        await self.t.handle(b,timers.parse('set a tea timer for five minutes'))
        self.assertIn('multiple timers',await self.t.handle(a,timers.parse('cancel timer')))
        old=self.t.items[a]['pasta']['end']
        await self.t.handle(a,timers.parse('add five minutes to the pasta timer'))
        changed=self.t.items[a]['pasta']['end']
        self.assertEqual((datetime.fromisoformat(changed)-datetime.fromisoformat(old)).total_seconds(),300)
        await self.t.handle(a,timers.parse('preview remove two minutes from the pasta timer'))
        self.assertEqual(self.t.items[a]['pasta']['end'],changed)
        await self.t.handle(a,timers.parse('remove two minutes from the pasta timer'))
        self.assertEqual((datetime.fromisoformat(self.t.items[a]['pasta']['end'])-datetime.fromisoformat(old)).total_seconds(),180)
        await self.t.handle(a,timers.parse('cancel my timers'))
        self.assertNotIn(a,self.t.items);self.assertIn(b,self.t.items)
    async def test_migrate_legacy_named_and_expire(self):
        a='assist_satellite.kitchen';end=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        await self.t.stop();Store.data={a:{'end':end,'name':'pasta'}}
        self.t=timers.Timers(self.hass);await self.t.start();await asyncio.sleep(.02)
        self.assertIn('pasta',self.hass.services.calls[-1][0][2]['message'])
        self.assertEqual(Store.data,{})
    async def test_removal_to_zero_announces(self):
        a='assist_satellite.kitchen'
        await self.t.handle(a,timers.parse('set a tea timer for five minutes'))
        await self.t.handle(a,timers.parse('remove ten minutes from the tea timer'))
        await asyncio.sleep(.02)
        self.assertIn('tea timer',self.hass.services.calls[-1][0][2]['message'])
        self.assertEqual(self.t.items,{})
    async def test_restore_and_announce(self):
        a='assist_satellite.kitchen';await self.t.handle(a,timers.parse('set a timer for five seconds'))
        await self.t.stop();self.t=timers.Timers(self.hass);await self.t.start();self.assertIn((a,''),self.t.tasks)
        await self.t.stop();Store.data={a:(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()}
        self.t=timers.Timers(self.hass);await self.t.start();await asyncio.sleep(.01)
        self.assertEqual(self.hass.services.calls[-1][0][0:2],('assist_satellite','announce'));self.assertEqual(Store.data,{})
    async def test_chat_cannot_silently_start_timer(self):
        response=await self.t.handle(None,timers.parse('set a timer for five minutes'))
        self.assertIn('voice satellite',response);self.assertFalse(self.t.items)
