import asyncio,copy,dataclasses,json,sys,types,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'custom_components'/'jarvis_voice_bridge'
pkg=types.ModuleType('bridge');pkg.__path__=[str(root)];sys.modules['bridge']=pkg
for name in ['homeassistant','homeassistant.components','wyoming']:
 m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
stt=types.ModuleType('homeassistant.components.stt')
class Entity:pass
@dataclasses.dataclass
class SpeechResult:text: str; result: str
stt.SpeechToTextEntity=Entity;stt.SpeechResult=SpeechResult;stt.SpeechResultState=types.SimpleNamespace(SUCCESS='success',ERROR='error')
sys.modules[stt.__name__]=stt
client=types.ModuleType('wyoming.client');client.AsyncTcpClient=object;sys.modules[client.__name__]=client
asr=types.ModuleType('wyoming.asr')
class Transcript:
 @staticmethod
 def is_type(t):return t=='transcript'
 @staticmethod
 def from_event(e):return types.SimpleNamespace(text=e.data['text'])
asr.Transcript=Transcript;asr.Transcribe=object;sys.modules[asr.__name__]=asr
audio=types.ModuleType('wyoming.audio');audio.AudioStart=audio.AudioChunk=audio.AudioStop=object;sys.modules[audio.__name__]=audio
error=types.ModuleType('wyoming.error');error.Error=type('Error',(),{'is_type':staticmethod(lambda t:t=='error')});sys.modules[error.__name__]=error
from bridge.stt import receive
class Event:
 def __init__(self,t,data):self.type=t;self.data=data
class Client:
 def __init__(self,events):self.events=iter(events)
 async def read_event(self):await asyncio.sleep(0);return next(self.events,None)
def req(name,conf,ident,text='good morning'):
 return Client([Event('jarvis-speaker',{'interaction_id':ident,'speaker':name,'confidence':conf}),Event('transcript',{'text':text})])
class Tests(unittest.IsolatedAsyncioTestCase):
 async def test_overlapping_identical_text_stays_matched(self):
  first,second=await asyncio.gather(receive(req('Jaco',.61,'one')),receive(req('Ed',.55,'two')))
  self.assertEqual(first.text.jarvis_speaker,('one','Jaco',.61));self.assertEqual(second.text.jarvis_speaker,('two','Ed',.55))
  self.assertEqual(json.dumps({'text':first.text}),'{"text": "good morning"}')
  self.assertEqual(copy.deepcopy(first.text).jarvis_speaker,first.text.jarvis_speaker)
 async def test_missing_or_invalid_identity_is_neutral(self):
  plain=await receive(Client([Event('transcript',{'text':'hello'})]))
  bad=await receive(req('Jaco',float('nan'),'one'))
  self.assertIsNone(plain.text.jarvis_speaker);self.assertIsNone(bad.text.jarvis_speaker)
 async def test_failure_has_no_identity(self):
  r=await receive(Client([Event('error',{})]));self.assertEqual(r.result,'error');self.assertIsNone(r.text)
if __name__=='__main__':unittest.main()
