"""Read-only sentence previews must never synthesize or persist audio."""
import unittest
import test_phrase_library as fixtures

class SentencePreview(unittest.IsolatedAsyncioTestCase):
    setUp=fixtures.PhraseTests.setUp
    generate=fixtures.PhraseTests.generate

    async def test_exact_order_pause_and_no_writes(self):
        await self.library.import_clips([('playing','wav',fixtures.audio(1000)),
                                        ('country','wav',fixtures.audio(2000)),
                                        ('kitchen.','wav',fixtures.audio(3000))],self.identity)
        before=await self.cache.snapshot()
        result=await self.library.preview(['Playing','country','kitchen.'],self.identity,100)
        self.assertEqual(result['missing'],[])
        pcm=fixtures.phrases.read_pcm(result['audio'])
        self.assertEqual(pcm[:4800],fixtures.phrases.read_pcm(fixtures.audio(1000)))
        self.assertEqual(pcm[4800:9600],b'\0'*4800)
        self.assertEqual(pcm[9600:14400],fixtures.phrases.read_pcm(fixtures.audio(2000)))
        self.assertEqual(pcm[-4800:],fixtures.phrases.read_pcm(fixtures.audio(3000)))
        self.assertEqual((await self.cache.snapshot())['bytes'],before['bytes'])
        self.assertEqual(self.calls,[])

    async def test_missing_clips_are_reported_without_partial_audio(self):
        await self.library.clip('country',self.identity,self.generate)
        self.calls.clear()
        result=await self.library.preview(['Playing','country','Kitchen.','Playing'],self.identity)
        self.assertEqual(result,{'missing':['playing','kitchen.']})
        self.assertEqual(self.calls,[])

    async def test_other_voice_never_supplies_preview_clip(self):
        await self.library.clip('country',self.identity,self.generate)
        result=await self.library.preview(['country'],{**self.identity,'voice_id':'other'})
        self.assertEqual(result,{'missing':['country']})

    async def test_limits_reject_invalid_requests(self):
        for parts,pause in [([],20),(['x']*9,20),([''],20),(['x'],True),(['x'],-1),(['x'],501),(['x'],1.5),('country',20)]:
            with self.subTest(parts=parts,pause=pause):
                with self.assertRaises(ValueError):await self.library.preview(parts,self.identity,pause)
        self.assertEqual((await self.cache.snapshot())['count'],0)

    async def test_corrupt_clip_never_calls_generator(self):
        identity=self.library.clip_identity(self.identity)
        await self.cache.store_audio(text='country',**identity,extension='wav',audio=b'invalid')
        with self.assertRaises((ValueError,EOFError,fixtures.phrases.wave.Error)):
            await self.library.preview(['country'],self.identity)
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()

