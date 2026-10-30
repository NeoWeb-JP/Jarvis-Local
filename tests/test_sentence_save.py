"""Save user-built sentences with missing-only generation and exact reuse."""
import unittest
from unittest.mock import patch
import test_phrase_library as fixtures

class SentenceSave(unittest.IsolatedAsyncioTestCase):
    setUp=fixtures.PhraseTests.setUp
    generate=fixtures.PhraseTests.generate

    async def test_missing_only_generation_and_full_sentence_saved(self):
        await self.library.clip('country',self.identity,self.generate)
        self.calls.clear()
        result=await self.library.save_sentence(['Playing','country','kitchen.'],self.identity,self.generate,100)
        self.assertEqual(self.calls,['playing','kitchen.'])
        self.assertEqual((result['generated_clips'],result['reused_clips'],result['saved']),(2,1,True))
        entry=next(e for e in (await self.cache.snapshot())['entries'] if e['kind']=='built_sentence')
        self.assertEqual(entry['parts'],['Playing','country','kitchen.']);self.assertEqual(entry['gap_ms'],100)
        saved=await self.cache.find_cached_audio(text='Playing country kitchen.',**self.identity)
        self.assertIsNotNone(saved)
        self.assertEqual(len(fixtures.phrases.read_pcm(saved[1])),3*4800+2*4800)
        self.calls.clear()
        repeated=await self.library.save_sentence(['Playing','country','kitchen.'],self.identity,self.generate)
        self.assertEqual(repeated['generated_clips'],0);self.assertEqual(self.calls,[])

    async def test_failure_keeps_valid_clips_but_not_partial_sentence(self):
        async def fail(text):
            if text=='country':raise RuntimeError('offline')
            return await self.generate(text)
        with self.assertRaises(RuntimeError):
            await self.library.save_sentence(['Playing','country'],self.identity,fail)
        entries=(await self.cache.snapshot())['entries']
        self.assertEqual([entry['kind'] for entry in entries],['clip'])
        self.assertIsNone(await self.cache.find_cached_audio(text='Playing country',**self.identity))
        self.calls.clear()
        await self.library.save_sentence(['Playing','country'],self.identity,self.generate)
        self.assertEqual(self.calls,['country'])

    async def test_bad_input_and_full_storage_do_not_generate(self):
        for parts,pause in [([],20),(['x']*9,20),(['x'],-1),([''],20)]:
            with self.assertRaises(ValueError):await self.library.save_sentence(parts,self.identity,self.generate,pause)
        self.cache.max_bytes=0
        with self.assertRaises(ValueError):await self.library.save_sentence(['country'],self.identity,self.generate)
        self.assertEqual(self.calls,[])

    async def test_replaces_old_mp3_only_after_successful_save(self):
        text='Playing country'
        await self.cache.store_audio(text=text,**self.identity,extension='mp3',audio=b'old recording')
        result=await self.library.save_sentence(['Playing','country'],self.identity,self.generate)
        self.assertTrue(result['saved'])
        saved=await self.cache.find_cached_audio(text=text,**self.identity)
        self.assertEqual(saved[0],'wav')
        self.assertFalse(any(self.cache.directory.rglob('*.mp3')))
        self.assertEqual(next(e['kind'] for e in (await self.cache.snapshot())['entries'] if e['text']==text),'built_sentence')

    async def test_failed_replacement_preserves_prior_audio(self):
        await self.cache.store_audio(text='country',**self.identity,extension='mp3',audio=b'old')
        self.cache.max_bytes=0
        saved=await self.cache.store_audio(text='country',**self.identity,extension='wav',audio=fixtures.audio())
        self.assertFalse(saved)
        self.assertEqual(await self.cache.find_cached_audio(text='country',**self.identity),('mp3',b'old'))

if __name__=='__main__':unittest.main()

