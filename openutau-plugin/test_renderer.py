"""Run native renderer checks against an installed OpenUtau, isolated from its UI.
python3 openutau-plugin/test_renderer.py --dotnet /path/to/dotnet [--real]
--real additionally requires the user's configured API, Wine and voicebank.
Build the plugin and Smoke project first. Uses a temporary port/data directory.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import zmq

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--dotnet', default=shutil.which('dotnet'))
parser.add_argument('--real', action='store_true')
parser.add_argument('--openutau-dir', default='/opt/openutau')
args = parser.parse_args()
if not args.dotnet: raise ValueError('Select an installed .NET runtime')
with tempfile.TemporaryDirectory(prefix='native-renderer-check-') as folder:
    root = Path(folder)
    with socket.socket() as probe: probe.bind(('127.0.0.1',0)); port = probe.getsockname()[1]
    config = root/'config.local.json'
    if args.real:
        config.write_text((ROOT/'bridge/config.local.json').read_text())
        voice = json.loads((ROOT/'bridge/voices.local.json').read_text())['voices'][0]
        script = ROOT/'enunu/server.py'
    else:
        config.write_text(json.dumps(dict(timeout_seconds=5)))
        voice = dict(comp_id='user-selected-test-voice',lang_id=4)
        script = root/'fake_backend.py'
        script.write_text('''import json,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0, ''' + repr(str(ROOT/'bridge')) + ''')
import host
from worker import make_sequence
def invoke(config,command,request,output):
    req=json.loads(Path(request).read_text());make_sequence(req)
    count=round(len(req['pitch_curve']['f0'])*5/1000*44100)
    frame=round(req['notes'][0]['position_ms']/5)
    bri=req['controller_curves']['brightness']['values'][frame]
    pcm=(np.sin(np.arange(count)*.1)*(1000+bri*10)).astype('<i2')
    with wave.open(str(output),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(pcm.tobytes())
host.invoke=invoke
import runpy
runpy.run_path(''' + repr(str(ROOT/'enunu/server.py')) + ''',run_name='__main__')
''')
    voicefile = root/'voice.local.json'; voicefile.write_text(json.dumps(voice))
    env = dict(os.environ,XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),OPENUTAU_DIR=args.openutau_dir)
    log = root/'server.log'
    with log.open('w') as output:
        process = subprocess.Popen([sys.executable,str(script),'--config',str(config),'--port',str(port)],
            stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            context=zmq.Context()
            with context.socket(zmq.REQ) as client:
                client.setsockopt(zmq.LINGER,0);client.connect(f'tcp://127.0.0.1:{port}')
                client.send_json(['ver_check'])
                if not client.poll(5000): raise RuntimeError(log.read_text())
                assert client.recv_json()['result']['version']=='2'
            context.term()
            Path(str(config)+'.service.local.json').write_text(json.dumps(dict(Ready=True,Pid=process.pid)))
            command=[args.dotnet,str(ROOT/'openutau-plugin/Smoke/bin/Release/net10.0/Smoke.dll'),
                '--expressions',str(ROOT/'openutau-plugin/bin/Release/net10.0/OpenUtau.Plugin.VocaloidBridge.dll'),
                str(config),str(root),str(port),str(voicefile)]
            result=subprocess.run(command,env=env,text=True,capture_output=True,timeout=180)
            print(result.stdout,end='')
            if result.returncode: raise RuntimeError(result.stderr+'\n'+log.read_text())
            assert log.read_text().count('PASS render') == 2, 'Cache reused/invalidated incorrectly'
        finally:
            os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
print('PASS:', 'real Wine/backend integration' if args.real else 'isolated protocol integration')
