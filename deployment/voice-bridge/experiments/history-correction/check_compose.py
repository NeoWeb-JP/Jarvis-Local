"""Verify a staged Compose override without printing resolved secrets."""
import json
import os
import sys


def check(before, after, running_mounts, stage):
    before = json.loads(json.dumps(before))
    after = json.loads(json.dumps(after))
    old = before.get('services', {}).get('voicepipeline')
    new = after.get('services', {}).get('voicepipeline')
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ValueError('VoicePipeline service missing from Compose model')
    old_volumes = old.pop('volumes', [])
    new_volumes = new.pop('volumes', [])
    if before != after:
        raise ValueError('Compose changes more than the target service volumes')
    expected = {
        '/app/api/main.py': os.path.join(stage, 'api.py'),
        '/app/ui/app.js': os.path.join(stage, 'ui.js'),
    }
    def indexed(volumes):
        result = {}
        for volume in volumes:
            if not isinstance(volume, dict) or not volume.get('target'):
                raise ValueError('Unexpected Compose volume format')
            target = volume['target']
            if target in result:
                raise ValueError('Duplicate volume target in Compose model')
            result[target] = volume
        return result
    old_by_target, new_by_target = indexed(old_volumes), indexed(new_volumes)
    if set(new_by_target) != set(old_by_target) | set(expected):
        raise ValueError('Compose volume targets differ from the expected additions')
    if set(old_by_target) & set(expected):
        raise ValueError('A target already exists in the original Compose configuration')
    for target, volume in old_by_target.items():
        if volume != new_by_target[target]:
            raise ValueError('An existing Compose volume was modified')
    for target, source in expected.items():
        v = new_by_target[target]
        if v.get('type') != 'bind' or os.path.realpath(v.get('source', '')) != os.path.realpath(source) or v.get('read_only') is not True:
            raise ValueError('A new application bind mount is incorrect')
    actual = {mount['Destination']: mount for mount in running_mounts}
    if len(actual) != len(running_mounts) or set(actual) != set(old_by_target):
        raise ValueError('Running mounts differ from the original Compose model')
    for target, volume in old_by_target.items():
        mount = actual[target]
        if volume.get('type') != 'bind' or mount.get('Type') != 'bind':
            raise ValueError('An existing mount is not a bind mount')
        if os.path.realpath(volume.get('source', '')) != os.path.realpath(mount.get('Source', '')):
            raise ValueError('A running mount source differs from Compose')
        if bool(volume.get('read_only', False)) != (not bool(mount.get('RW', True))):
            raise ValueError('A running mount access mode differs from Compose')
    image = old.get('image')
    if not isinstance(image, str) or not image:
        raise ValueError('Compose service has no explicit image')
    return image


if __name__ == '__main__':
    if len(sys.argv) != 5:
        raise SystemExit('Usage: check_compose.py BEFORE AFTER MOUNTS STAGE')
    try:
        with open(sys.argv[1], encoding='utf-8') as f: before = json.load(f)
        with open(sys.argv[2], encoding='utf-8') as f: after = json.load(f)
        with open(sys.argv[3], encoding='utf-8') as f: mounts = json.load(f)
        image = check(before, after, mounts, sys.argv[4])
        print('Compose model differs only by the two intended read-only app mounts.')
        print('Existing running mount paths and access modes match the baseline Compose model.')
        print('Compose image:', image)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit('Compose check failed: ' + str(exc))
