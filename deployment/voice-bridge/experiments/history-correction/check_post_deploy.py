"""Check that deployment preserves existing mounts and adds two read-only files."""
import json
import os
import sys


def check(before, after, stage):
    def index(mounts):
        result = {}
        for mount in mounts:
            target = mount.get('Destination')
            if not target or target in result:
                raise ValueError('Missing or duplicate mount target')
            result[target] = mount
        return result
    old, new = index(before), index(after)
    expected = {'/app/api/main.py': os.path.join(stage, 'api.py'),
                '/app/ui/app.js': os.path.join(stage, 'ui.js')}
    if set(old) & set(expected) or set(new) != set(old) | set(expected):
        raise ValueError('Deployed mount targets differ from the expected set')
    for target, mount in old.items():
        current = new[target]
        if (mount.get('Type'), os.path.realpath(mount.get('Source', '')), bool(mount.get('RW'))) != (
            current.get('Type'), os.path.realpath(current.get('Source', '')), bool(current.get('RW'))
        ):
            raise ValueError('An existing mount changed during deployment')
    for target, source in expected.items():
        mount = new[target]
        if mount.get('Type') != 'bind' or mount.get('RW') is not False or os.path.realpath(mount.get('Source', '')) != os.path.realpath(source):
            raise ValueError('A new application mount is incorrect')
    return True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: check_post_deploy.py BEFORE_MOUNTS AFTER_MOUNTS STAGE')
    try:
        with open(sys.argv[1], encoding='utf-8') as stream: before = json.load(stream)
        with open(sys.argv[2], encoding='utf-8') as stream: after = json.load(stream)
        check(before, after, sys.argv[3])
        print('Existing mounts preserved; corrected app files mounted read-only.')
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit('Deployed mount check failed: ' + str(exc))
