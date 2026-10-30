"""Search the full private recording inventory without changing saved audio."""
import json
import unittest
import test_phrase_library as fixtures

class RecordingSearch(unittest.IsolatedAsyncioTestCase):
    setUp=fixtures.PhraseTests.setUp
    generate=fixtures.PhraseTests.generate

    async def test_case_insensitive_phrase_search_keeps_palette_and_totals(self):
        await self.library.clip('country',self.identity,self.generate)
        await self.library.clip('kitchen.',self.identity,self.generate)
        before=await self.cache.snapshot()
        found=await self.cache.snapshot(query='  COUNTRY  ')
        self.assertEqual([e['text'] for e in found['entries']],['country'])
        self.assertEqual(found['matched_count'],1)
        self.assertEqual(len(found['palette_entries']),2)
        self.assertEqual((found['count'],found['bytes']),(before['count'],before['bytes']))

    async def test_search_includes_older_recordings_outside_display_limit(self):
        for index in range(205):
            path=self.cache.path_for(f'{index:064x}','wav')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(fixtures.audio())
            path.with_suffix('.wav.json').write_text(json.dumps({'text':'old office' if index==0 else f'phrase {index}',
                'kind':'clip','provider':'tts.elevenlabs','voice_id':'declan','created':index}),encoding='utf-8')
        self.assertEqual(len((await self.cache.snapshot())['entries']),200)
        found=await self.cache.snapshot(query='old office')
        self.assertEqual([e['text'] for e in found['entries']],['old office'])
        self.assertEqual(found['count'],205)

    async def test_metadata_search_and_no_matches(self):
        await self.library.clip('country',self.identity,self.generate)
        for query in ['clip','tts.elevenlabs','declan']:
            self.assertEqual((await self.cache.snapshot(query=query))['matched_count'],1)
        missing=await self.cache.snapshot(query='missing phrase')
        self.assertEqual(missing['entries'],[]);self.assertEqual(missing['matched_count'],0)
        self.assertEqual(missing['count'],1)
        self.assertEqual((await self.cache.snapshot(query=''))['matched_count'],1)

    async def test_invalid_queries_rejected(self):
        for query in [None,123,'x'*201]:
            with self.assertRaises(ValueError):await self.cache.snapshot(query=query)

    async def test_ten_per_page_and_complete_last_page(self):
        for index in range(23):
            path=self.cache.path_for(f'{index:064x}','wav')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(fixtures.audio())
            path.with_suffix('.wav.json').write_text(json.dumps({'text':f'phrase {index}',
                'kind':'clip','created':index}),encoding='utf-8')
        pages=[await self.cache.snapshot(page=page) for page in [1,2,3]]
        self.assertEqual([len(page['entries']) for page in pages],[10,10,3])
        self.assertEqual([(page['first'],page['last']) for page in pages],[(1,10),(11,20),(21,23)])
        self.assertEqual({entry['key'] for page in pages for entry in page['entries']},
                         {f'{index:064x}' for index in range(23)})
        self.assertTrue(all(page['page_count']==3 for page in pages))
        self.assertTrue(all(len(page['palette_entries'])==23 for page in pages))
        self.assertEqual((await self.cache.snapshot(page=999))['page'],3)
        found=await self.cache.snapshot(query='phrase 1',page=2)
        self.assertEqual(found['matched_count'],11);self.assertEqual(len(found['entries']),1)
        self.assertEqual((found['first'],found['last']),(11,11))

    async def test_empty_page_and_invalid_page_parameters(self):
        empty=await self.cache.snapshot(page=99)
        self.assertEqual((empty['page'],empty['page_count'],empty['first'],empty['last']),(1,1,0,0))
        for page in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):await self.cache.snapshot(page=page)
        with self.assertRaises(ValueError):await self.cache.snapshot(page=1,page_size=0)

if __name__=='__main__':unittest.main()



