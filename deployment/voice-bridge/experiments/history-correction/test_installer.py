"""Exercise isolated installer paths with fake Docker and a temporary filesystem."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / 'test_fixtures'

FAKE_DOCKER = r'''#!/usr/bin/env python3
import hashlib, os, re, shutil, sys
from pathlib import Path
root = Path(os.environ['FAKE_ROOT'])
args = sys.argv[1:]
cmd = args.pop(0)
def obj(path):
    return root / 'container' / path.lstrip('/')
def mounted(value):
    if ':' in value and value.startswith('voicepipeline-isolated-test:'):
        return obj(value.split(':', 1)[1])
    return Path(value)
if cmd == 'inspect':
    name = args[0]; fmt = args[-1]
    if '.State.Running' in fmt:
        print((root / 'state').read_text().strip())
    elif '.Image' in fmt:
        print('sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55')
    elif 'println .Destination' in fmt:
        print('/data\n/models\n/app/pipeline/models/speaker_id.py')
    else:
        target = re.search(r'eq .Destination "([^"]+)"', fmt).group(1)
        base = root / ('live' if name == 'voicepipeline' else 'test')
        print(base / target.lstrip('/'))
elif cmd == 'exec':
    if args[0] == '-i': args.pop(0)
    args.pop(0)
    if args[0] == 'sha256sum':
        data = obj(args[1]).read_bytes()
        print(hashlib.sha256(data).hexdigest(), args[1])
    elif args[0] == 'python' and args[1] == '-':
        sys.stdout.buffer.write(b'isolated fixture backup')
elif cmd == 'cp':
    src, dst = args
    marker = root / 'inject-failure'
    if marker.exists() and src.startswith('/tmp/jarvis-correction.') and dst.endswith('/app/ui/app.js'):
        marker.unlink(); print('Injected copy failure', file=sys.stderr); sys.exit(1)
    shutil.copyfile(mounted(src), mounted(dst))
elif cmd == 'stop':
    (root / 'state').write_text('false')
elif cmd in ('start', 'restart'):
    (root / 'state').write_text('true')
else:
    raise SystemExit('Unexpected docker call: ' + cmd)
'''
FAKE_CURL = r'''#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
url = args[args.index('-fsS') + 1]
destination = args[args.index('-o') + 1]
shutil.copyfile(Path(os.environ['FAKE_CANDIDATE']) / url.rsplit('/', 1)[1], destination)
'''


class InstallerTests(unittest.TestCase):
    def test_install_and_failure_restore(self):
        for legacy, inject_failure in ((False, False), (False, True), (True, False), (True, True)):
            with self.subTest(legacy=legacy, inject_failure=inject_failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for folder in ('live/data', 'live/models', 'test/data', 'test/models', 'container/app/api', 'container/app/ui', 'bin'):
                    (root / folder).mkdir(parents=True)
                (root / 'state').write_text('true')
                if inject_failure: (root / 'inject-failure').touch()
                old_api = UPSTREAM / ('legacy-api.py' if legacy else 'api.py')
                old_ui = UPSTREAM / ('legacy-ui.js' if legacy else 'ui.js')
                (root / 'container/app/api/main.py').write_bytes(old_api.read_bytes())
                (root / 'container/app/ui/app.js').write_bytes(old_ui.read_bytes())
                for name, content in [('docker', FAKE_DOCKER), ('curl', FAKE_CURL)]:
                    target = root / 'bin' / name
                    target.write_text(content)
                    target.chmod(0o755)
                script = (HERE / 'install-isolated.sh').read_text()
                script = script.replace('/opt/voicepipeline-isolated-test', str(root / 'test'))
                script = script.replace('/opt/voicepipeline', str(root / 'live'))
                script_path = root / 'install.sh'
                script_path.write_text(script)
                env = dict(os.environ, FAKE_ROOT=str(root), FAKE_CANDIDATE=str(HERE),
                           PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'])
                result = subprocess.run(['sh', str(script_path)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, not inject_failure, result.stdout + result.stderr)
                expected_api = old_api if inject_failure else HERE / 'api.py'
                expected_ui = old_ui if inject_failure else HERE / 'ui.js'
                self.assertEqual((root / 'container/app/api/main.py').read_bytes(), expected_api.read_bytes())
                self.assertEqual((root / 'container/app/ui/app.js').read_bytes(), expected_ui.read_bytes())
                self.assertEqual((root / 'state').read_text(), 'true')
                self.assertTrue(list((root / 'test').glob('history-correction-backup.*/speaker.db')))


if __name__ == '__main__':
    unittest.main()
