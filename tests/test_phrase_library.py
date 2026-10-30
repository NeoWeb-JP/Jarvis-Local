"""Persistent phrase reuse, exact wording, audio assembly and storage limits."""
import asyncio
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'custom_components'/'jarvis_local'
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

phrases=load('phrase_library')
VoiceCache=load('voice_cache').VoiceCache

def audio(sample=1000):
    return phrases.pcm_wave(struct.pack('<h',sample)*2400)

class PhraseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.cache=VoiceCache(self.directory.name,min_free_bytes=0)
        self.library=phrases.PhraseLibrary(self.cache)
        self.identity=dict(provider='tts.elevenlabs',voice_id='v1:declan',model='flash',language='en',settings={})
        self.calls=[]
    async def generate(self,text):
        self.calls.append(text)
        return 'wav',audio(1000+len(self.calls))

    async def test_new_genre_generates_only_genre(self):
        first=await self.library.compose('Playing country music from Spotify in the kitchen.',self.identity,self.generate)
        self.assertEqual(first[3],4)
        self.calls.clear()
        second=await self.library.compose('Playing jazz music from Spotify in the kitchen.',self.identity,self.generate)
        self.assertEqual(self.calls,['jazz']);self.assertEqual(second[3],1)
        pcm=phrases.read_pcm(second[1]);self.assertGreater(len(pcm),2400*2*4)
        self.calls.clear()
        repeated=await self.library.compose('Playing jazz music from Spotify in the kitchen.',self.identity,self.generate)
        self.assertTrue(repeated[2]);self.assertEqual(self.calls,[])

    async def test_room_reuse_survives_restart_and_case(self):
        await self.library.clip('Kitchen.',self.identity,self.generate)
        self.library=phrases.PhraseLibrary(VoiceCache(self.directory.name,min_free_bytes=0))
        self.calls.clear()
        await self.library.compose('I requested country in kitchen.',self.identity,self.generate)
        self.assertNotIn('kitchen.',self.calls)
        self.calls.clear()
        await self.library.compose('I requested country in bedroom.',self.identity,self.generate)
        self.assertEqual(self.calls,['bedroom.'])

    async def test_voice_model_provider_language_settings_are_isolated(self):
        await self.library.clip('country',self.identity,self.generate)
        for field,value in [('voice_id','v2:other'),('provider','tts.xtts'),('model','other'),('language','fr'),('settings',{'speed':1.1})]:
            self.calls.clear()
            await self.library.clip('country',{**self.identity,field:value},self.generate)
            self.assertEqual(self.calls,['country'])

    async def test_concurrent_different_sentences_share_paid_clips(self):
        await asyncio.gather(*[self.library.compose(
            f'Playing {genre} music from Spotify in the kitchen.',self.identity,self.generate)
            for genre in ['country','jazz','rock','country']])
        self.assertEqual(self.calls.count('playing'),1)
        self.assertEqual(self.calls.count('kitchen.'),1)
        self.assertEqual(len(self.calls),6)

    async def test_failure_retains_completed_clips_without_caching_sentence(self):
        async def fail(text):
            if text=='country':raise RuntimeError('offline')
            return await self.generate(text)
        with self.assertRaises(RuntimeError):
            await self.library.compose('I requested country in kitchen.',self.identity,fail)
        snapshot=await self.cache.snapshot()
        self.assertEqual([e['kind'] for e in snapshot['entries']],['clip'])
        self.calls.clear()
        await self.library.compose('I requested country in kitchen.',self.identity,self.generate)
        self.assertNotIn('i requested',self.calls)

    async def test_unrecognised_text_is_never_rewritten(self):
        for message in ['Do not play country music.', 'Playing country music from Spotify in the kitchen. Actually stop.',
                        'The kitchen light failed.', 'It is 20 degrees.', 'Playing jazz in the kitchen?', 'I requested country in kitchen. Then stop.']:
            self.assertIsNone(await self.library.compose(message,self.identity,self.generate))
        self.assertEqual(self.calls,[])

    def test_order_and_boundaries(self):
        first=audio(1000);second=audio(2000)
        pcm=phrases.read_pcm(phrases.join_clips([first,second]))
        self.assertEqual(pcm[:4800],phrases.read_pcm(first))
        self.assertEqual(pcm[-4800:],phrases.read_pcm(second))
        self.assertEqual(phrases.phrase_parts('I requested country in kitchen.'),['I requested','country','in','kitchen.'])
        self.assertEqual(phrases.phrase_parts('Playing country music from Spotify in the kitchen.'),['Playing','country','music from Spotify in the','kitchen.'])

    def test_rejects_malformed_or_silent_audio(self):
        for value in [b'invalid',phrases.pcm_wave(b'\0\0'*100)]:
            with self.assertRaises((ValueError,EOFError,phrases.wave.Error)):
                phrases.join_clips([value])

    async def test_silent_provider_audio_is_not_saved(self):
        async def silent(text):return 'wav',phrases.pcm_wave(b'\0\0'*100)
        with self.assertRaises(ValueError):
            await self.library.clip('country',self.identity,silent)
        self.assertEqual((await self.cache.snapshot())['count'],0)

    async def test_full_disk_protects_existing_recordings(self):
        await self.library.clip('country',self.identity,self.generate)
        before=await self.cache.snapshot()
        self.cache.max_bytes=before['bytes']
        await self.library.clip('jazz',self.identity,self.generate)
        after=await self.cache.snapshot()
        self.assertEqual(after['count'],1);self.assertEqual(after['skipped_writes'],1)
        self.assertEqual(after['bytes'],before['bytes'])
        self.calls.clear();await self.library.clip('country',self.identity,self.generate)
        self.assertEqual(self.calls,[])

    async def test_free_space_reserve_and_concurrent_budget(self):
        self.cache.min_free_bytes=10**30
        await self.library.clip('country',self.identity,self.generate)
        self.assertEqual((await self.cache.snapshot())['count'],0)
        self.cache.min_free_bytes=0;self.cache.max_bytes=6500
        await asyncio.gather(*[self.library.clip(text,self.identity,self.generate) for text in ['jazz','rock','pop']])
        snapshot=await self.cache.snapshot()
        self.assertLessEqual(snapshot['bytes'],6500);self.assertEqual(snapshot['count'],1)

    async def test_preview_key_cannot_escape_cache(self):
        with self.assertRaises(ValueError):await self.cache.saved_audio('../secrets','wav')
        with self.assertRaises(ValueError):await self.cache.saved_audio('a'*64,'../json')

    async def test_real_decoder_when_ffmpeg_available(self):
        import shutil
        binary=shutil.which('ffmpeg')
        if not binary:self.skipTest('FFmpeg is not installed on this test host')
        proc=await asyncio.create_subprocess_exec(binary,'-loglevel','error','-i','pipe:0','-f','mp3','pipe:1',
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        mp3,_=await proc.communicate(audio());self.assertEqual(proc.returncode,0)
        converted=await phrases.normalise_audio('mp3',mp3,binary)
        self.assertGreater(len(phrases.read_pcm(converted)),0)

if __name__=='__main__':unittest.main()

