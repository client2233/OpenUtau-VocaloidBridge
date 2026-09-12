"""ENUNU external-wave adapter; real synthesis is performed by VOCALOID."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import wave
import numpy as np
import zmq
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from host import invoke

PERIOD = 5.0


def score(path):
    settings, blocks, current = {}, [], None
    for line in Path(path).read_text(encoding='shift_jis').splitlines():
        if line.startswith('[#'):
            if line == '[#SETTING]': current = settings
            elif line == '[#TRACKEND]': current = None
            else:
                current = {}; blocks.append(current)
        elif current is not None and '=' in line:
            key, value = line.split('=',1); current[key] = value
    tempo = float(settings['Tempo'])
    if not 0 < tempo <= 1000: raise ValueError('Invalid UST tempo')
    voice = json.loads((Path(settings['VoiceDir'])/'bridge.voice.json').read_text())
    cursor, notes = 0, []
    frame_segments = []
    for block in blocks:
        length = int(block['Length'])
        if length < 0: raise ValueError('Invalid UST note length')
        start = cursor / 480 * 60000 / tempo
        cursor += length
        end = cursor / 480 * 60000 / tempo
        lyric = block['Lyric']
        frame_segments.append((start,end,0 if lyric=='R' else int(block['NoteNum'])))
        if lyric != 'R':
            notes.append(dict(position_ms=start,duration_ms=end-start,tone=int(block['NoteNum']),
                              lyric=lyric, velocity=max(0, min(127, round(float(block.get('Velocity', 100)) * 64 / 100)))))
    return voice, notes, frame_segments, cursor / 480 * 60000 / tempo


def acoustic(path):
    voice, notes, segments, duration = score(path)
    frames = round(duration / PERIOD)
    f0 = np.zeros(frames,dtype=np.float64)
    for start,end,tone in segments:
        if tone:
            f0[round(start/PERIOD):round(end/PERIOD)] = 440*2**((tone-69)/12)
    root = Path(str(Path(path).with_suffix(''))+'_enutemp'); root.mkdir(parents=True,exist_ok=True)
    np.save(root/'f0.npy',f0)
    # These are protocol markers only: the selected external synthe branch never
    # reads mel/vuv data. No NNSVS acoustic model or vocoder is involved.
    np.save(root/'mel.npy',np.empty(0,dtype=np.float64)); np.save(root/'vuv.npy',(f0>0).astype(np.float64))
    return dict(path_f0=str(root/'f0.npy'),path_mel=str(root/'mel.npy'),path_vuv=str(root/'vuv.npy'))


def synthe(config,path,output):
    voice,notes,segments,duration = score(path)
    root=Path(str(Path(path).with_suffix(''))+'_enutemp')
    f0=np.load(root/'editorf0.npy').tolist()
    request=dict(protocol=1,comp_id=voice['comp_id'],lang_id=voice['lang_id'],notes=notes,
                 pitch_curve=dict(frame_period_ms=PERIOD,f0=f0))
    with tempfile.TemporaryDirectory(prefix='v6-enu-') as folder:
        temp=Path(folder); (temp/'request.json').write_text(json.dumps(request))
        invoke(config,'render',temp/'request.json',temp/'raw.wav')
        with wave.open(str(temp/'raw.wav')) as wav:
            assert wav.getframerate()==44100 and wav.getnchannels()==1 and wav.getsampwidth()==2
            count=round(len(f0)*PERIOD/1000*44100)
            data=wav.readframes(count)
        data += b'\0' * max(0,count*2-len(data))
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(output),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(44100);wav.writeframes(data)
    return dict(path_wav=output)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--port',type=int,default=15556)
    args=parser.parse_args();config=str(Path(args.config).resolve())
    ctx=zmq.Context(); socket=ctx.socket(zmq.REP)
    ports=[args.port] + ([15555] if args.port==15556 else [])
    try:
        for port in ports: socket.bind(f'tcp://127.0.0.1:{port}')
    except Exception:
        socket.close();ctx.term();raise
    print(f'ENUNU VOCALOID bridge ready at {ports}',flush=True)
    try:
        while True:
            request=socket.recv_json()
            try:
                command=request[0]
                if command=='ver_check':result=dict(name='VOCALOID Wine Bridge',version='1',author='Local adapter')
                elif command=='acoustic':result=acoustic(request[1])
                elif command=='synthe':result=synthe(config,request[1],request[2])
                else:raise ValueError('Unsupported ENUNU command: '+command)
                socket.send_json(dict(error=None,result=result));print('PASS',command,flush=True)
            except Exception as error:
                socket.send_json(dict(error=str(error),result={}));print('ERROR',str(error),flush=True)
    except KeyboardInterrupt:
        pass
    finally:socket.close();ctx.term()
