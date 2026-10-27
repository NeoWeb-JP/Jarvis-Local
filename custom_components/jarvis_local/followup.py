"""Exact follow-up forms with no inferred target names."""
import re
from .text import percentages

def followup(text):
    text=percentages(text).lower().replace('’',"'").strip().rstrip('.?!')
    text=re.sub(r'^(?:hey[\s,]+)?jarvis[\s,:.!?]+','',text)
    preview=False
    for prefix in ['preview ','dry run ','what would you do if i said ']:
        if text.startswith(prefix):preview=True;text=text[len(prefix):];break
    m=re.fullmatch(r'(?:please )?(?:turn|switch) (?:them|it) (on|off)(?: please)?',text)
    if m:return 'turn '+m[1]+' __previous_lights__',preview
    m=re.fullmatch(r'(?:please )?(?:turn|switch) (on|off) (?:them|it)(?: please)?',text)
    if m:return 'turn '+m[1]+' __previous_lights__',preview
    m=re.fullmatch(r'(?:please )?set (?:them|it) to (\d+(?:\.\d+)?) (?:percent|%)(?: please)?',text)
    if m:return 'set __previous_lights__ to '+m[1]+' percent',preview
    m=re.fullmatch(r'(?:make (?:them|it) |(?:a bit |a little )?)(brighter|dimmer)',text)
    if m:return ('brighten' if m[1]=='brighter' else 'dim')+' __previous_lights__',preview
    m=re.fullmatch(r'(dim|brighten) (?:them|it)',text)
    if m:return m[1]+' __previous_lights__',preview
    return None
