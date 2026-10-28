"""Safe diagnostic conversation agent for the bridge test pipeline."""
from homeassistant.components import conversation
from homeassistant.helpers import intent
from .models import SpeakerTranscript

async def async_setup_entry(hass,entry,async_add_entities):
    async_add_entities([BridgeTestAgent(entry)])

class BridgeTestAgent(conversation.ConversationEntity):
    _attr_name='Jarvis Voice Bridge Test'
    def __init__(self,entry):self._attr_unique_id=entry.entry_id+'-test-conversation'
    @property
    def supported_languages(self):return ['en']
    async def async_process(self,user_input):
        text=user_input.text
        speaker=text.jarvis_speaker if isinstance(text,SpeakerTranscript) else None
        if speaker:
            _,name,confidence=speaker
            response=f'I heard {text}. Speaker match: {name}, confidence {round(confidence*100)} percent.'
        else:
            response=f'I heard {text}. No speaker identification reached the test agent.'
        result=intent.IntentResponse(language=user_input.language)
        result.async_set_speech(response)
        return conversation.ConversationResult(response=result,conversation_id=user_input.conversation_id)
