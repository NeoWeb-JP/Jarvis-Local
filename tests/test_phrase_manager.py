"""Exercise the real TTS wrapper with controlled Home Assistant providers."""
import asyncio
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_phrase_library import audio, VoiceCache

ROOT=Path(__file__).resolve().parents[1]/'custom_components'/'jarvis_local'

class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        package=types.ModuleType('phrase_manager_fixture');package.__path__=[str(ROOT)]
        fake_tts=types.ModuleType('homeassistant.components.tts');fake_tts.TextToSpeechEntity=type('TextToSpeechEntity',(),{})
        fake_ffmpeg=types.ModuleType('homeassistant.components.ffmpeg')
        fake_ffmpeg.get_ffmpeg_manager=lambda hass:types.SimpleNamespace(binary='ffmpeg')
        exceptions=types.ModuleType('homeassistant.exceptions')
        exceptions.HomeAssistantError=type('HomeAssistantError',(Exception,),{})
        self.modules={'phrase_manager_fixture':package,'homeassistant.components.tts':fake_tts,
                      'homeassistant.components.ffmpeg':fake_ffmpeg,'homeassistant.exceptions':exceptions}
        for name in ['homeassistant','homeassistant.components']:
            stub=types.ModuleType(name);stub.__path__=[];self.modules[name]=stub
        self.modules['homeassistant.components'].tts=fake_tts
        # Keep all stubs scoped to this test; other repository fixtures coexist.
        self.patcher=patch.dict(sys.modules,self.modules);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.module=importlib.import_module('phrase_manager_fixture.tts')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cache=VoiceCache(self.temp.name,min_free_bytes=0)
        self.entry=types.SimpleNamespace(entry_id='test',options={'primary_tts':'tts.elevenlabs','fallback_tts':'tts.xtts','elevenlabs_voice':'declan','cache_revision':'v1','category_fallback':False})
        self.usage=self.module.VoiceUsage()
        self.manager=self.module.JarvisVoiceManager(self.entry,self.cache,self.usage)
        self.manager.entity_id='tts.jarvis_voice_manager'
        self.manager.hass=types.SimpleNamespace()
        self.calls=[]
        async def generate(hass,**kwargs):
            self.calls.append((kwargs['provider_entity_id'],kwargs['text']))
            return 'wav',audio()
        self.generate=generate
        self.provider_patch=patch.object(self.module,'generate_from_existing_tts',generate)
        self.provider_patch.start();self.addCleanup(self.provider_patch.stop)

    async def test_real_music_reply_uses_segments_then_only_new_genre(self):
        first=await self.manager.async_get_tts_audio('I requested country in kitchen.','en',{})
        self.assertEqual(first[0],'wav');self.assertEqual(len(self.calls),4)
        self.calls.clear()
        await self.manager.async_get_tts_audio('I requested jazz in kitchen.','en',{})
        self.assertEqual(self.calls,[('tts.elevenlabs','jazz')])
        self.assertEqual(self.usage.snapshot()['last_source'],'elevenlabs_phrase_generated')
        self.assertEqual(self.usage.snapshot()['generated_clips'],5)
        self.calls.clear()
        await self.manager.async_get_tts_audio('I requested jazz in kitchen.','en',{})
        self.assertEqual(self.calls,[])
        self.assertEqual(self.usage.snapshot()['last_source'],'elevenlabs_phrase_cached')

    async def test_explicit_whole_sentence_is_preferred_and_preview_does_not_run_music(self):
        text='I requested country in kitchen.'
        await self.manager.prepare_phrase(text,'sentence')
        self.assertEqual(self.calls,[('tts.elevenlabs',text)])
        self.calls.clear()
        await self.manager.async_get_tts_audio(text,'en',{})
        self.assertEqual(self.calls,[])
        self.assertEqual(self.usage.snapshot()['last_source'],'elevenlabs_cached')

    async def test_primary_failure_falls_back_for_entire_original_message(self):
        text='I requested country in kitchen.'
        async def fail(hass,**kwargs):
            self.calls.append((kwargs['provider_entity_id'],kwargs['text']))
            if kwargs['provider_entity_id']=='tts.elevenlabs':raise self.module.HomeAssistantError('offline')
            return 'wav',audio(2000)
        with patch.object(self.module,'generate_from_existing_tts',fail):
            result=await self.manager.async_get_tts_audio(text,'en',{})
        self.assertEqual(self.calls,[('tts.elevenlabs','i requested'),('tts.xtts',text)])
        self.assertEqual(result[1],audio(2000))
        self.assertEqual(self.usage.snapshot()['last_source'],'xtts_generated')

    async def test_conversion_failure_uses_original_full_sentence(self):
        async def broken(*args):raise ValueError('bad audio')
        self.manager._phrases.normalise=broken
        text='I requested country in kitchen.'
        await self.manager.async_get_tts_audio(text,'en',{})
        self.assertEqual(self.calls[-1],('tts.elevenlabs',text))

    async def test_disabled_library_and_unknown_text_use_whole_sentences(self):
        self.entry.options['phrase_library_enabled']=False
        text='I requested country in kitchen.'
        await self.manager.async_get_tts_audio(text,'en',{})
        self.assertEqual(self.calls,[('tts.elevenlabs',text)])
        self.calls.clear();self.entry.options['phrase_library_enabled']=True
        await self.manager.async_get_tts_audio('Kitchen light did not respond.','en',{})
        self.assertEqual(self.calls,[('tts.elevenlabs','Kitchen light did not respond.')])

    async def test_admin_generation_checks_storage_and_validation_first(self):
        for text,kind in [('', 'clip'),('x'*201,'clip'),('hello','unknown')]:
            with self.assertRaises(ValueError):await self.manager.prepare_phrase(text,kind)
        self.cache.min_free_bytes=10**30
        with self.assertRaises(ValueError):await self.manager.prepare_phrase('country','clip')
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()

