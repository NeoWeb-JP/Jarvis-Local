"""A plain visible transcript with per-request in-process identity metadata."""
class SpeakerTranscript(str):
    def __new__(cls,text,speaker=None):
        obj=super().__new__(cls,text)
        obj.jarvis_speaker=speaker
        return obj
    def __reduce_ex__(self,protocol):
        return (type(self),(str(self),self.jarvis_speaker))
