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

if __name__=='__main__':unittest.main()

