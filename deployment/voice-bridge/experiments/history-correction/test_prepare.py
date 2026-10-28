"""Simulate production staging, including redaction and Compose drift."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
r = Path(os.environ['FAKE_ROOT']); args = sys.argv[1:]; cmd = args.pop(0)
with (r / 'calls').open('a') as f: f.write(cmd + '\n')
image = 'sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
root = r / 'live'
mounts = [
 {'Destination': '/data', 'Source': str(root/'data'), 'Type':'bind', 'RW':True},
 {'Destination': '/models', 'Source': str(root/'models'), 'Type':'bind', 'RW':True},
 {'Destination': '/app/pipeline/wyoming_server.py', 'Source': str(root/'jarvis-bridge-wyoming.py'), 'Type':'bind', 'RW':False},
 {'Destination': '/app/pipeline/models/speaker_id.py', 'Source': str(root/'jarvis-speaker-cache-fix.py'), 'Type':'bind', 'RW':False},
]
if cmd == 'inspect':
 fmt = args[-1]
 if '.State.Running' in fmt: print('true')
 elif '.Image' in fmt: print(image)
 elif 'com.docker.compose.project.config_files' in fmt:
  print(','.join(str(root/x) for x in ['compose.yaml','compose.override.yaml','compose.bridge-test.yaml','compose.cache-test.yaml']))
 elif 'com.docker.compose.project.working_dir' in fmt: print(root)
 elif 'com.docker.compose.project' in fmt or 'com.docker.compose.service' in fmt: print('voicepipeline')
 elif 'json .Mounts' in fmt: print(json.dumps(mounts))
 else: raise SystemExit('unexpected inspect format '+fmt)
elif cmd == 'exec':
 name, program, filename = args
 table = {
  ('voicepipeline','/app/api/main.py'): '83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386',
  ('voicepipeline','/app/ui/app.js'): 'e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1',
  ('voicepipeline','/app/pipeline/models/speaker_id.py'): 'fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f',
  ('voicepipeline-isolated-test','/app/api/main.py'): '56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47',
  ('voicepipeline-isolated-test','/app/ui/app.js'): 'bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87',
 }
 print(table[(name,filename)], filename)
elif cmd == 'compose':
 service={'image':'voicepipeline-whisper:local','environment':{'SECRET':'DO_NOT_EXPOSE'},'volumes':[]}
 for m in mounts:
  v={'type':'bind','source':m['Source'],'target':m['Destination']}
  if not m['RW']: v['read_only']=True
  service['volumes'].append(v)
 files=[args[i+1] for i,x in enumerate(args) if x=='-f']
 if len(files)==5:
  stage=Path(files[-1]).parent
  service['volumes'] += [
   {'type':'bind','source':str(stage/'api.py'),'target':'/app/api/main.py','read_only':True},
   {'type':'bind','source':str(stage/'ui.js'),'target':'/app/ui/app.js','read_only':True}]
  if os.getenv('FAKE_DRIFT')=='1': service['environment']['SECRET']='CHANGED_SECRET'
 print(json.dumps({'name':'voicepipeline','services':{'voicepipeline':service}}))
elif cmd == 'image': print(image)
else: raise SystemExit('unexpected docker command '+cmd)
'''
FAKE_CURL = r'''#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
args=sys.argv[1:]; url=args[args.index('-fsS')+1]; out=args[args.index('-o')+1]
shutil.copyfile(Path(os.environ['FAKE_CANDIDATE']) / url.rsplit('/',1)[1], out)
'''


class PrepareTests(unittest.TestCase):
    def test_safe_stage_and_compose_drift(self):
        for drift in (False, True):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); live = root / 'live'
                for folder in (live, live/'data', live/'models', root/'bin'): folder.mkdir(parents=True, exist_ok=True)
                for name in ('compose.yaml','compose.override.yaml','compose.bridge-test.yaml','compose.cache-test.yaml','jarvis-speaker-cache-fix.py','jarvis-bridge-wyoming.py'):
                    (live/name).write_text('fixture')
                (live/'.env').write_text('SECRET=DO_NOT_EXPOSE')
                for name, content in [('docker',FAKE_DOCKER),('curl',FAKE_CURL)]:
                    target=root/'bin'/name; target.write_text(content); target.chmod(0o755)
                script=(HERE/'prepare-production.sh').read_text().replace('/opt/voicepipeline',str(live))
                file=root/'prepare.sh'; file.write_text(script)
                env=dict(os.environ, FAKE_ROOT=str(root), FAKE_CANDIDATE=str(HERE), FAKE_DRIFT='1' if drift else '0', PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
                result=subprocess.run(['sh',str(file)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode==0, not drift, result.stdout+result.stderr)
                self.assertNotIn('DO_NOT_EXPOSE',result.stdout+result.stderr)
                self.assertNotIn('CHANGED_SECRET',result.stdout+result.stderr)
                self.assertTrue(set((root/'calls').read_text().splitlines()).isdisjoint({'stop','start','restart','up'}))
                stage=next(live.glob('history-correction-stage.*'))
                self.assertEqual(list(stage.glob('private.*')), [])
                self.assertEqual((stage/'source-checksums.txt').exists(), not drift)


if __name__ == '__main__': unittest.main()
