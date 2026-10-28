"""Local voice profiles; preserve unrelated fields and never expose secrets."""
import json
import math
import os
from pathlib import Path
import re
import tempfile


def validate_profiles(profiles):
    if not isinstance(profiles, dict) or len(profiles) > 30:
        raise ValueError('Provide at most 30 profiles.')
    result = {}
    names = set()
    for key, value in profiles.items():
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9 _-]{0,79}', key):
            raise ValueError('Speaker keys must be lowercase letters, numbers, spaces, hyphens or underscores.')
        if not isinstance(value, dict) or set(value) - {'name', 'min_confidence', 'morning_responses'}:
            raise ValueError('Invalid profile fields.')
        name = value.get('name')
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ '-]{0,39}", name):
            raise ValueError('Each profile needs a valid display name.')
        if name.casefold() in names:
            raise ValueError('Display names must be unique.')
        names.add(name.casefold())
        threshold = value.get('min_confidence', 0.75)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError('Confidence must be between 0 and 1.')
        phrases = value.get('morning_responses', [])
        if not isinstance(phrases, list) or len(phrases) > 50 or any(not isinstance(p, str) or not p.strip() or len(p) > 500 for p in phrases):
            raise ValueError('Each profile may have up to 50 non-empty responses of 500 characters.')
        result[key] = {'name': name, 'min_confidence': threshold, 'morning_responses': [p.strip() for p in phrases]}
    return result


def public_profiles(config):
    profiles = config.get('profiles', {}) if isinstance(config, dict) else {}
    return {key: {k: val[k] for k in ('name','min_confidence','morning_responses') if k in val}
            for key, val in profiles.items() if isinstance(key, str) and isinstance(val, dict)} if isinstance(profiles, dict) else {}


def save_profiles_file(path, profiles):
    path = Path(path)
    try:
        with path.open(encoding='utf-8') as stream:
            config = json.load(stream)
    except FileNotFoundError:
        config = {}
    if not isinstance(config, dict):
        raise ValueError('Voice ID configuration must be an object.')
    # Retain unknown profile fields for forward compatibility.
    old = config.get('profiles', {})
    config['profiles'] = {key: {**(old.get(key, {}) if isinstance(old, dict) and isinstance(old.get(key), dict) else {}), **value}
                          for key, value in profiles.items()}
    fd, temporary = tempfile.mkstemp(prefix='.jarvis_voice_id_', dir=path.parent)
    try:
        if path.exists(): os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return config
