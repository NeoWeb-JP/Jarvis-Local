"""Validate private, bounded audio imports without calling a speech provider."""
import base64
import binascii
from hashlib import sha256
import re

MAX_CLIPS = 32
MAX_AUDIO_BYTES = 2*1024*1024
MAX_PACK_BYTES = 8*1024*1024


def decode_clips(clips):
    if not isinstance(clips,list) or not 1 <= len(clips) <= MAX_CLIPS:
        raise ValueError('Import between 1 and 32 recordings at a time')
    decoded=[];seen=set();total=0
    for clip in clips:
        if not isinstance(clip,dict):raise ValueError('Invalid recording')
        text=clip.get('text')
        if not isinstance(text,str) or not 1 <= len(text.strip()) <= 80 or re.search(r'[\x00-\x1f\x7f]',text):
            raise ValueError('Each recording needs a phrase of 1 to 80 characters')
        text=text.strip().casefold()
        if text in seen:raise ValueError('Duplicate phrase: '+text)
        seen.add(text)
        extension=clip.get('extension')
        if extension not in {'mp3','wav','ogg','flac'}:raise ValueError('Unsupported recording format')
        encoded=clip.get('audio')
        if not isinstance(encoded,str) or len(encoded) > 4*((MAX_AUDIO_BYTES+2)//3):
            raise ValueError('Recording exceeds 2 MiB')
        try:audio=base64.b64decode(encoded,validate=True)
        except (binascii.Error,ValueError) as err:raise ValueError('Invalid recording data') from err
        if not audio or len(audio) > MAX_AUDIO_BYTES:raise ValueError('Recording is empty or exceeds 2 MiB')
        total+=len(audio)
        if total > MAX_PACK_BYTES:raise ValueError('Recordings exceed the 8 MiB import limit')
        if 'sha256' in clip and clip['sha256'] != sha256(audio).hexdigest():
            raise ValueError('Recording checksum does not match: '+text)
        decoded.append((text,extension,audio))
    return decoded

