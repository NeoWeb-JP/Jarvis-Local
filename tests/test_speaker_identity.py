from unittest import mock
import base64,hashlib,hmac,json,unittest
import test_commands
from jarvis_test.speaker_identity import unwrap
SECRET='test-secret';NOW=1700000000
PROFILES={'jaco':{'name':'Jaco','min_confidence':0.5},'edd':{'name':'Ed','min_confidence':0.5}}
def marker(speaker,ident,text='good morning',confidence=0.6,when=NOW):
    p={'id':ident,'speaker':speaker,'confidence':confidence,'time':when,'text':text}
    e=base64.urlsafe_b64encode(json.dumps(p,separators=(',',':')).encode()).decode().rstrip('=')
    return 'JVS1.'+e+'.'+hmac.new(SECRET.encode(),e.encode(),hashlib.sha256).hexdigest()
class SpeakerTests(unittest.TestCase):
    def test_interleaved_distinct_requests(self):
        seen={};a=marker('Jaco','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');b=marker('Edd','bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
        self.assertEqual(unwrap(b,SECRET,PROFILES,seen,NOW),('good morning','Ed'))
        self.assertEqual(unwrap(a,SECRET,PROFILES,seen,NOW),('good morning','Jaco'))
        self.assertEqual(unwrap(a,SECRET,PROFILES,seen,NOW),('',None))
    def test_uncertain_and_unknown_keep_text(self):
        self.assertEqual(unwrap(marker('Jaco','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',confidence=.3),SECRET,PROFILES,{},NOW),('good morning',None))
        self.assertEqual(unwrap(marker('unknown','bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),SECRET,PROFILES,{},NOW),('good morning',None))
    def test_tampered_and_stale_never_execute(self):
        token=marker('Jaco','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
        self.assertEqual(unwrap(token, 'wrong',PROFILES,{},NOW),('',None))
        self.assertEqual(unwrap(token,SECRET,PROFILES,{},NOW+31),('',None))
    def test_ordinary_transcript_unchanged(self):self.assertEqual(unwrap('lamp on',SECRET,PROFILES,{},NOW),('lamp on',None))
if __name__=='__main__':unittest.main()

class BridgeProfileTests(unittest.TestCase):
    def test_bridge_match_and_threshold(self):
        import sys, types
        from jarvis_test.speaker_identity import bridge_profile
        bridge = types.ModuleType('custom_components.jarvis_voice_bridge.models')
        class SpeakerTranscript(str):
            def __new__(cls, text, identity):
                value = super().__new__(cls, text)
                value.jarvis_speaker = identity
                return value
        bridge.SpeakerTranscript = SpeakerTranscript
        with mock.patch.dict(sys.modules, {'custom_components.jarvis_voice_bridge.models': bridge}):
            profiles = {'jaco': {'name': 'Jaco', 'min_confidence': 0.6}}
            self.assertEqual(bridge_profile(SpeakerTranscript('hello', ('id', 'Jaco', 0.7)), profiles), 'Jaco')
            self.assertIsNone(bridge_profile(SpeakerTranscript('hello', ('id', 'Jaco', 0.5)), profiles))
            self.assertIsNone(bridge_profile(SpeakerTranscript('hello', ('id', 'Jaco', float('nan'))), profiles))
            self.assertIsNone(bridge_profile('hello', profiles))
