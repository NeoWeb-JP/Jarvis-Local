"""Read installed build metadata from the integration manifest."""
import json
from pathlib import Path


def read_version():
    """Called in Home Assistant's executor during entry setup and reload."""
    with (Path(__file__).parent / 'manifest.json').open(encoding='utf-8') as stream:
        version = json.load(stream)['version']
    if not isinstance(version, str) or not version.strip():
        raise ValueError('Jarvis manifest version must be a non-empty string')
    return version
