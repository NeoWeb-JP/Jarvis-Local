"""Audio imports reuse the clip identity without provider generation."""
import base64
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

import test_phrase_library as fixtures
from test_phrase_library import audio, load
decode_clips=load('phrase_import').decode_clips

def clip(text='kitchen.',payload=None):
    payload=audio() if payload is None else payload
    return {'text':text,'extension':'wav','audio':base64.b64encode(payload).decode('ascii'),
            'sha256':sha256(payload).hexdigest()}

class ImportValidation(unittest.TestCase):
    def test_round_trip_and_checksum(self):
        text,extension,payload=decode_clips([clip('Kitchen.')])[0]
        self.assertEqual((text,extension,payload),('kitchen.','wav',audio()))
        bad=clip();bad['sha256']='wrong'
        with self.assertRaises(ValueError):decode_clips([bad])

    def test_rejects_bad_metadata_before_decoding(self):
        badcases=[[],[clip()]*33,[clip('')],[clip('kitchen.\n')],
                  [clip('Kitchen.'),clip('kitchen.')],
                  [{**clip(),'extension':'exe'}],[{**clip(),'audio':'not base64!'}],
                  [{**clip(),'audio':'A'*2796205}]]
        for value in badcases:
            with self.subTest(value=str(value)[:80]):
                with self.assertRaises(ValueError):decode_clips(value)

class ImportReuse(unittest.IsolatedAsyncioTestCase):
    setUp=fixtures.PhraseTests.setUp
    generate=fixtures.PhraseTests.generate
    async def test_import_then_compose_never_generates_room(self):
        result=await self.library.import_clips(decode_clips([clip()]),self.identity)
        self.assertEqual(result,{'imported':['kitchen.'],'existing':[],'not_saved':[]})
        self.assertEqual(self.calls,[])
        await self.library.compose('I requested country in kitchen.',self.identity,self.generate)
        self.assertNotIn('kitchen.',self.calls)
        self.assertEqual(len(self.calls),3)

    async def test_import_is_idempotent_and_preserves_existing_audio(self):
        await self.library.clip('kitchen.',self.identity,self.generate)
        before=await self.cache.find_cached_audio(text='kitchen.',**self.library.clip_identity(self.identity))
        result=await self.library.import_clips(decode_clips([clip(payload=audio(3000))]),self.identity)
        after=await self.cache.find_cached_audio(text='kitchen.',**self.library.clip_identity(self.identity))
        self.assertEqual(result['existing'],['kitchen.']);self.assertEqual(before,after)

    async def test_invalid_later_clip_leaves_no_partial_import(self):
        items=decode_clips([clip(),clip('study.',audio(0))])
        with self.assertRaises(ValueError):await self.library.import_clips(items,self.identity)
        self.assertEqual((await self.cache.snapshot())['count'],0)

    async def test_import_respects_budget_before_any_write(self):
        self.cache.max_bytes=1
        with self.assertRaises(ValueError):
            await self.library.import_clips(decode_clips([clip()]),self.identity)
        self.assertEqual((await self.cache.snapshot())['count'],0)

    async def test_write_failures_are_reported_without_losing_successes(self):
        save=self.cache._save
        async def fail_one(path,payload,metadata):
            if metadata['text']=='study.':raise OSError('unavailable')
            return await save(path,payload,metadata)
        with patch.object(self.cache,'_save',fail_one):
            result=await self.library.import_clips(decode_clips([clip(),clip('study.')]),self.identity)
        self.assertEqual(result['imported'],['kitchen.'])
        self.assertEqual(result['not_saved'],['study.'])

    async def test_import_survives_restart_and_uses_current_voice_only(self):
        await self.library.import_clips(decode_clips([clip()]),self.identity)
        snapshot=await self.cache.snapshot()
        self.assertEqual(snapshot['entries'][0]['kind'],'imported_clip')
        self.calls.clear()
        self.library=fixtures.phrases.PhraseLibrary(fixtures.VoiceCache(self.directory.name,min_free_bytes=0))
        await self.library.clip('kitchen.',self.identity,self.generate)
        self.assertEqual(self.calls,[])
        await self.library.clip('kitchen.',{**self.identity,'voice_id':'different'},self.generate)
        self.assertEqual(self.calls,['kitchen.'])

if __name__=='__main__':unittest.main()

