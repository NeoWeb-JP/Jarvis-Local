"""Exercise production deployment and rollback with fake Docker only."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'test_fixtures'
FAKE_DOCKER = r'''#!/usr/bin/env python3
import hashlib, json, os, shutil, sys
from pathlib import Path
r=Path(os.environ['FAKE_ROOT']); root=r/'live'; stage=Path(os.environ['FAKE_STAGE'])
args=sys.argv[1:]; cmd=args.pop(0); state=(r/'state').read_text().strip()
with (r/'calls').open('a') as f: f.write(cmd+'\n')
image='sha256:aefd844361f6816721a5497d25eefbfdf670e33df81c0e16dde533f68e510a55'
mounts=[
 {'Destination':'/data','Source':str(root/'data'),'Type':'bind','RW':True},
 {'Destination':'/models','Source':str(root/'models'),'Type':'bind','RW':True},
 {'Destination':'/app/pipeline/wyoming_server.py','Source':str(root/'jarvis-bridge-wyoming.py'),'Type':'bind','RW':False},
 {'Destination':'/app/pipeline/models/speaker_id.py','Source':str(root/'jarvis-speaker-cache-fix.py'),'Type':'bind','RW':False}]
extras=[{'Destination':'/app/api/main.py','Source':str(stage/'api.py'),'Type':'bind','RW':False},
        {'Destination':'/app/ui/app.js','Source':str(stage/'ui.js'),'Type':'bind','RW':False}]
service={'image':'voicepipeline-whisper:local','environment':{'TOKEN':'DO_NOT_EXPOSE'},
 'ports':[{'target':8000,'published':'8000','protocol':'tcp'},{'target':10300,'published':'10300','protocol':'tcp'}],
 'networks':{'default':None},'volumes':[]}
for m in mounts:
 v={'type':'bind','source':m['Source'],'target':m['Destination']}
 if not m['RW']: v['read_only']=True
 service['volumes'].append(v)
def model(new=False):
 s=json.loads(json.dumps(service))
 if new:
  for m in extras: s['volumes'].append({'type':'bind','source':m['Source'],'target':m['Destination'],'read_only':True})
 return {'name':'voicepipeline','services':{'voicepipeline':s},'networks':{'default':{'name':'voicepipeline_default'}}}
def container():
 return {'Image':image,'Config':{'Env':['PATH=/bin','TOKEN=DO_NOT_EXPOSE']},
 'HostConfig':{'PortBindings':{'8000/tcp':[{'HostIp':'','HostPort':'8000'}],
 '10300/tcp':[{'HostIp':'','HostPort':'10300'}]}},
 'NetworkSettings':{'Networks':{'voicepipeline_default':{}}}}
if cmd=='inspect':
 if '--format' not in args: print(json.dumps([container()]))
 else:
  fmt=args[-1]
  if '.State.Running' in fmt: print('true')
  elif '.Image' in fmt: print(image)
  elif 'json .Mounts' in fmt: print(json.dumps(mounts+(extras if state=='new' else [])))
  elif 'com.docker.compose.project.config_files' in fmt:
   files=[str(root/x) for x in ['compose.yaml','compose.override.yaml','compose.bridge-test.yaml','compose.cache-test.yaml']]
   if state=='new': files.append(str(stage/'compose.history-correction.yaml'))
   print(','.join(files))
  elif 'com.docker.compose.project.working_dir' in fmt: print(root)
  elif 'com.docker.compose.project' in fmt or 'com.docker.compose.service' in fmt: print('voicepipeline')
  else: raise SystemExit('unexpected inspect '+fmt)
elif cmd=='exec':
 if args[0]=='-i': args.pop(0)
 args.pop(0); program=args.pop(0)
 if program=='python': sys.stdout.buffer.write((r/'snapshot.db').read_bytes())
 elif program=='sha256sum':
  path=args[0]
  if path.endswith('speaker_id.py'): digest='fb5c6f04121e61a4ae1e7d84cc8615c22eaa032aaa58154bf324952f98c9640f'
  elif path.endswith('main.py'): digest=('56a085ecf601ba243d908f9acfd19fd175cb4ed5f411b58b50b6893f9c782a47' if state=='new' else '83b8285bc91b451fcf1e1b80db141cf9d3f1620026186d7f511f128066e8c386')
  else: digest=('bd8584122297456d6b7a67112f030ed62a72aae8485b68201ad2dea086e66e87' if state=='new' else 'e4156a695b1c6a20e8a1700a565b3070918174fd805d1fd9aeb87cb1066d7be1')
  if state=='new' and os.getenv('FAKE_FAIL')=='1' and path.endswith('main.py'): digest='bad'
  print(digest,path)
elif cmd=='cp':
 src,dst=args; name='api.py' if src.endswith('main.py') else 'ui.js'
 shutil.copyfile(Path(os.environ['FAKE_FIXTURES'])/name,dst)
elif cmd=='compose':
 files=[args[i+1] for i,x in enumerate(args) if x=='-f']; new=len(files)==5
 if 'config' in args: print(json.dumps(model(new)))
 elif 'up' in args:
  with (r/'calls').open('a') as f: f.write('up-new\n' if new else 'up-old\n')
  (r/'state').write_text('new' if new else 'old')
 elif 'ps' in args:
  (r/'wrapper-args.json').write_text(json.dumps(args))
 else: raise SystemExit('unexpected compose call')
elif cmd=='image':
 if '--format' in args: print(image)
 else: print(json.dumps([{'Id':image,'Config':{'Env':['PATH=/bin']}}]))
elif cmd=='diff': print('C /app\nA /app/__pycache__')
else: raise SystemExit('unexpected docker command '+cmd)
'''
FAKE_CURL = r'''#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
args=sys.argv[1:]
if any('127.0.0.1:8000' in a for a in args): raise SystemExit(0)
url=args[args.index('-fsS')+1]; out=args[args.index('-o')+1]
shutil.copyfile(Path(os.environ['FAKE_CANDIDATE'])/url.rsplit('/',1)[1],out)
'''


class DeployTests(unittest.TestCase):
    def test_deploy_rollback_and_drift_guard(self):
        for failure, drift, layer_drift in ((False,False,False),(True,False,False),(False,True,False),(False,False,True)):
            with self.subTest(failure=failure, drift=drift, layer_drift=layer_drift), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); live=root/'live'; stage=live/'history-correction-stage.fixture'
                for folder in (live, live/'data',live/'models',stage,root/'bin'): folder.mkdir(parents=True,exist_ok=True)
                (root/'state').write_text('old')
                sources=[]
                for name in ('compose.yaml','compose.override.yaml','compose.bridge-test.yaml','compose.cache-test.yaml','jarvis-speaker-cache-fix.py','jarvis-bridge-wyoming.py','.env'):
                    p=live/name; p.write_text('SECRET=DO_NOT_EXPOSE' if name=='.env' else 'fixture'); sources.append(p)
                for name in ('api.py','ui.js','check_compose.py'):
                    p=stage/name; p.write_bytes((HERE/name).read_bytes()); sources.append(p)
                p=stage/'compose.history-correction.yaml'; p.write_text('fixture'); sources.append(p)
                (stage/'source-checksums.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p}\n' for p in sources))
                (stage/'reviewed-container-diff.txt').write_text('changed\n' if layer_drift else 'A /app/__pycache__\nC /app\n')
                if drift: (live/'compose.yaml').write_text('changed')
                with sqlite3.connect(root/'snapshot.db') as db:
                    db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
                    db.executemany('INSERT INTO settings VALUES (?,?)', [('match_threshold','0.47'),('speaker_match_thresholds',json.dumps({'jaco':.5,'ed':.47}))])
                for name,content in [('docker',FAKE_DOCKER),('curl',FAKE_CURL)]:
                    p=root/'bin'/name; p.write_text(content); p.chmod(0o755)
                script=(HERE/'deploy-production.sh').read_text().replace('/opt/voicepipeline',str(live))
                path=root/'deploy.sh'; path.write_text(script)
                env=dict(os.environ, FAKE_ROOT=str(root), FAKE_STAGE=str(stage), FAKE_CANDIDATE=str(HERE), FAKE_FIXTURES=str(FIXTURES), FAKE_FAIL='1' if failure else '0', PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
                result=subprocess.run(['sh',str(path),str(stage)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode==0,not failure and not drift and not layer_drift,result.stdout+result.stderr)
                self.assertNotIn('DO_NOT_EXPOSE',result.stdout+result.stderr)
                calls=(root/'calls').read_text().splitlines()
                self.assertEqual('up-new' in calls, not drift and not layer_drift)
                self.assertEqual('up-old' in calls, failure)
                self.assertEqual((root/'state').read_text(), 'new' if not failure and not drift and not layer_drift else 'old')
                if not drift and not layer_drift:
                    self.assertTrue(list(stage.glob('before-deploy.*/speaker.db')))
                    wrapper=next(stage.glob('compose-with-history.*'))
                    check=subprocess.run(['sh','-n',str(wrapper)],capture_output=True,text=True)
                    self.assertEqual(check.returncode,0,check.stderr)
                    self.assertIn('"$@"',wrapper.read_text())
                    if not failure:
                        call=subprocess.run(['sh',str(wrapper),'ps','-a'],env=env,capture_output=True,text=True)
                        self.assertEqual(call.returncode,0,call.stderr)
                        args=json.loads((root/'wrapper-args.json').read_text())
                        self.assertEqual(args.count('-f'),5)
                        self.assertEqual(args[-2:],['ps','-a'])

    def test_manual_rollback_preserves_data_and_speaker_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); live=root/'live'; stage=live/'history-correction-stage.fixture'
            for folder in (live,live/'data',live/'models',stage,root/'bin'): folder.mkdir(parents=True,exist_ok=True)
            (root/'state').write_text('new')
            sources=[]
            for name in ('compose.yaml','compose.override.yaml','compose.bridge-test.yaml','compose.cache-test.yaml','jarvis-speaker-cache-fix.py','jarvis-bridge-wyoming.py'):
                p=live/name; p.write_text('fixture'); sources.append(p)
            for name in ('api.py','ui.js','check_compose.py'):
                p=stage/name; p.write_bytes((HERE/name).read_bytes()); sources.append(p)
            p=stage/'compose.history-correction.yaml'; p.write_text('fixture'); sources.append(p)
            (stage/'source-checksums.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p}\n' for p in sources))
            (live/'data'/'speaker.db').write_bytes(b'current recordings and settings')
            for name,content in [('docker',FAKE_DOCKER),('curl',FAKE_CURL)]:
                p=root/'bin'/name; p.write_text(content); p.chmod(0o755)
            script=(HERE/'rollback-production.sh').read_text().replace('/opt/voicepipeline',str(live))
            path=root/'rollback.sh'; path.write_text(script)
            env=dict(os.environ,FAKE_ROOT=str(root),FAKE_STAGE=str(stage),FAKE_CANDIDATE=str(HERE),FAKE_FIXTURES=str(FIXTURES),FAKE_FAIL='0',PATH=str(root/'bin')+os.pathsep+os.environ['PATH'])
            result=subprocess.run(['sh',str(path),str(stage)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual((root/'state').read_text(),'old')
            self.assertEqual((live/'data'/'speaker.db').read_bytes(),b'current recordings and settings')
            self.assertEqual((live/'jarvis-speaker-cache-fix.py').read_text(),'fixture')
            self.assertNotIn('DO_NOT_EXPOSE',result.stdout+result.stderr)


if __name__ == '__main__': unittest.main()
