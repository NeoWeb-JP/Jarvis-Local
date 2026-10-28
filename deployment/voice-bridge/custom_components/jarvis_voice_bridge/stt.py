"""Wyoming STT bridge retaining the speaker result for the same connection."""
import asyncio
import logging
import math
from collections.abc import AsyncIterable
from homeassistant.components import stt
from wyoming.client import AsyncTcpClient
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.error import Error
from .models import SpeakerTranscript
_LOGGER=logging.getLogger(__name__)

async def async_setup_entry(hass,entry,async_add_entities):
    async_add_entities([VoiceBridge(entry)])

async def upload(client,stream):
    async for data in stream:
        await client.write_event(AudioChunk(rate=16000,width=2,channels=1,audio=data).event())
    await client.write_event(AudioStop().event())

async def receive(client):
    identity=None
    while event:=await client.read_event():
        if event.type=='jarvis-speaker':
            value=event.data or {}
            name=value.get('speaker');confidence=value.get('confidence');identity_id=value.get('interaction_id')
            if isinstance(name,str) and name and len(name)<=80 and isinstance(identity_id,str) and len(identity_id)<=80 and isinstance(confidence,(int,float)) and not isinstance(confidence,bool) and math.isfinite(confidence) and 0<=confidence<=1:
                identity=(identity_id,name,confidence)
        elif Transcript.is_type(event.type):
            return stt.SpeechResult(SpeakerTranscript(Transcript.from_event(event).text,identity),stt.SpeechResultState.SUCCESS)
        elif Error.is_type(event.type):
            return stt.SpeechResult(None,stt.SpeechResultState.ERROR)
    return stt.SpeechResult(None,stt.SpeechResultState.ERROR)

class VoiceBridge(stt.SpeechToTextEntity):
    _attr_name='Jarvis Voice Bridge'
    def __init__(self,entry):
        self.host=entry.data['host'];self.port=entry.data['port'];self._attr_unique_id=entry.entry_id+'-stt'
    @property
    def supported_languages(self):return ['en']
    @property
    def supported_formats(self):return [stt.AudioFormats.WAV]
    @property
    def supported_codecs(self):return [stt.AudioCodecs.PCM]
    @property
    def supported_bit_rates(self):return [stt.AudioBitRates.BITRATE_16]
    @property
    def supported_sample_rates(self):return [stt.AudioSampleRates.SAMPLERATE_16000]
    @property
    def supported_channels(self):return [stt.AudioChannels.CHANNEL_MONO]
    async def async_process_audio_stream(self,metadata,stream:AsyncIterable[bytes]):
        try:
            async with AsyncTcpClient(self.host,self.port) as client:
                await client.write_event(Transcribe(language=metadata.language).event())
                await client.write_event(AudioStart(rate=16000,width=2,channels=1).event())
                upload_task=asyncio.create_task(upload(client,stream))
                receive_task=asyncio.create_task(receive(client))
                try:
                    done,_=await asyncio.wait((upload_task,receive_task),return_when=asyncio.FIRST_COMPLETED)
                    if receive_task in done:return receive_task.result()
                    upload_task.result()
                    return await receive_task
                finally:
                    for task in (upload_task,receive_task):
                        if not task.done():task.cancel()
                    await asyncio.gather(upload_task,receive_task,return_exceptions=True)
        except (OSError,TimeoutError):
            _LOGGER.exception('Voice bridge could not reach speech service')
            return stt.SpeechResult(None,stt.SpeechResultState.ERROR)
