"""Allow only the reviewed ephemeral paths in a Docker writable-layer diff."""
import re
import sys

ROOT = '/usr/local/lib/python3.12'
STDLIB = ('', 'zoneinfo', 'ctypes', 'sqlite3', 'multiprocessing', 'asyncio',
          'unittest', 'concurrent', 'concurrent/futures')
APP = ('/app/pipeline', '/app/pipeline/models', '/app/api')
cache_dirs = {ROOT + ('/' + sub if sub else '') + '/__pycache__' for sub in STDLIB}
cache_dirs.update(path + '/__pycache__' for path in APP)
changed_dirs = {'/usr', '/usr/local', '/usr/local/lib', ROOT, '/root', '/app',
                '/app/pipeline', '/app/pipeline/models', '/app/api'}
changed_dirs.update(ROOT + '/' + sub for sub in STDLIB if sub)
registry = {'/root/.cache', '/root/.cache/huggingface',
            '/root/.cache/huggingface/.agent_harnesses.json'}


def check(lines):
    for line in lines:
        line = line.rstrip('\n')
        if not line:
            continue
        if len(line) < 3 or line[1] != ' ':
            raise ValueError('Docker diff contains an unexpected entry')
        status, path = line[0], line[2:]
        if status == 'C' and path in changed_dirs:
            continue
        if status in ('A', 'C') and path in cache_dirs:
            continue
        if status == 'A' and path in registry:
            continue
        if status == 'A' and '/' in path:
            parent, name = path.rsplit('/', 1)
            if parent in cache_dirs and re.fullmatch(r'[A-Za-z0-9_.-]+\.cpython-312\.pyc', name):
                continue
        raise ValueError('Docker diff includes an unreviewed change')
    return True


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: check_writable_diff.py DOCKER_DIFF')
    try:
        with open(sys.argv[1], encoding='utf-8') as stream:
            check(stream)
        print('Writable-layer changes are limited to the reviewed caches.')
    except (ValueError, OSError) as exc:
        raise SystemExit('Writable-layer check failed: ' + str(exc) + '; run docker diff voicepipeline for review.')
