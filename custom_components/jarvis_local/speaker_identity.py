"""Authenticate speaker metadata bound to one transcript; never use for access control."""
import base64
import hashlib
import hmac
import json
import math
import re
import time


def unwrap(text, secret, profiles, seen, now=None):
    if not isinstance(text,str) or not text.startswith('JVS1.'):
        return text,None
    if not isinstance(secret,str) or not secret:
        return '',None
    match=re.fullmatch(r'JVS1\.([A-Za-z0-9_-]{1,8192})\.([a-f0-9]{64})',text)
    if not match:return '',None
    encoded,signature=match.groups()
    expected=hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature,expected):return '',None
    try:
        payload=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
        transcript=payload['text'];speaker=payload['speaker'];confidence=payload['confidence'];stamp=payload['time'];ident=payload['id']
        if not isinstance(transcript,str) or not isinstance(speaker,str) or not isinstance(ident,str) or not re.fullmatch(r'[0-9a-fA-F-]{36}',ident):return '',None
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:return '',None
        if isinstance(stamp,bool) or not isinstance(stamp,int):return '',None
        now=time.time() if now is None else now
        for key,expiry in list(seen.items()):
            if expiry<now:seen.pop(key,None)
        if abs(now-stamp)>30 or ident in seen:return '',None
        seen[ident]=now+60
        if len(seen)>512:seen.pop(next(iter(seen)))
        profile=profiles.get(speaker.casefold()) if isinstance(profiles,dict) else None
        if not isinstance(profile,dict):return transcript,None
        threshold=profile.get('min_confidence',0.75);name=profile.get('name')
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<=threshold<=1:return transcript,None
        if confidence<threshold or not isinstance(name,str) or not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ '-]{0,39}",name):return transcript,None
        return transcript,name
    except (ValueError,TypeError,KeyError,UnicodeDecodeError):return '',None
