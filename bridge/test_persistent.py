"""Check worker reuse, shutdown, timeout and optional real-engine equivalence."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from host import Worker, invoke, enable_persistent, close_worker

parser = argparse.ArgumentParser()
parser.add_argument('--real', action='store_true')
args = parser.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    script = root/'fake.py'
    script.write_text('''import json,sys,os,time
for line in sys.stdin:
 r=json.loads(line)
 if r.get('command')=='shutdown': break
 if 'timeout' in r['request']: time.sleep(.2)
 print(json.dumps({'ok':True,'pid':os.getpid()}),flush=True)
''')
    worker = Worker([sys.executable, str(script)], dict(os.environ))
    pid = worker.process.pid
    try:
        assert worker.render(root/'a', root/'out', 1)['pid'] == pid
        assert worker.render(root/'b', root/'out', 1)['pid'] == pid
        try:
            worker.render(root/'timeout', root/'out', .01)
            raise AssertionError('Timeout ignored')
        except TimeoutError:
            pass
    finally:
        worker.close()
    assert worker.process.poll() is not None
    print('PASS: process reuse, timeout and graceful shutdown')
    if args.real:
        config = Path(__file__).with_name('config.local.json')
        voices = invoke(config, 'list')['voices']
        voice = next(v for v in voices if v['lang_id'] == 4)
        score = dict(protocol=1, comp_id=voice['comp_id'], lang_id=4,
            notes=[dict(position_ms=500,duration_ms=500,tone=60,lyric='a',velocity=64)],
            pitch_curve=dict(frame_period_ms=5,f0=[0]*100+[261.625565]*100+[0]*100))
        request = root/'request.json';request.write_text(json.dumps(score))
        times = []
        outputs = []
        try:
            for i in range(3):
                if i == 1: enable_persistent()
                output = root/f'{i}.wav'
                start=time.monotonic();invoke(config,'render',request,output)
                times.append(time.monotonic()-start);outputs.append(output.read_bytes())
            assert outputs[0] == outputs[1] == outputs[2], 'Reused engine changed identical synthesis'
            score['controller_curves'] = {'brightness': {'frame_period_ms':5, 'values':[0]*300}}
            request.write_text(json.dumps(score))
            changed = root/'changed.wav';invoke(config,'render',request,changed)
            import host
            host._persistent = False
            fresh = root/'fresh.wav';invoke(config,'render',request,fresh)
            assert changed.read_bytes() == fresh.read_bytes(), 'Reused engine retained stale controller state'
            print('PASS: controller edit matches fresh worker synthesis')
            print('PASS: real cold/warm synthesis byte-identical; seconds:', ', '.join(f'{t:.3f}' for t in times))
        finally:
            close_worker()
