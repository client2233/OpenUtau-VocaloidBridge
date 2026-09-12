"""Run: python3 bridge/test_score.py"""
import json
from pathlib import Path
from worker import make_sequence

request = json.loads(Path(__file__).with_name('request.example.json').read_text())
score = make_sequence(request)
notes = score['tracks'][0]['parts'][0]['notes']
assert [note['number'] for note in notes] == [60, 62, 64]
assert notes[0]['pos'] == 720 and notes[0]['duration'] == 480
request['notes'][1]['position_ms'] = 700
try:
    make_sequence(request)
except ValueError:
    pass
else:
    raise AssertionError('Overlapping notes accepted')
print('PASS: timing conversion and invalid overlap rejection')

request['notes'] = [dict(position_ms=i*1000/93.75, duration_ms=1000/93.75,
    tone=60, lyric='la', phoneme='l a') for i in range(30)]
score = make_sequence(request)
notes = score['tracks'][0]['parts'][0]['notes']
assert all(a['pos']+a['duration'] == b['pos'] for a,b in zip(notes,notes[1:]))
request['pitch_curve'] = dict(frame_period_ms=1000/93.75, f0=[440*2**((62-69)/12)]*30)
controllers = make_sequence(request)['tracks'][0]['parts'][0]['controllers']
assert controllers[0]['events'][0]['value'] == 12
assert all(event['value'] == round(2/12*8192) for event in controllers[1]['events'])
request['pitch_curve']['f0'][0] = float('nan')
try: make_sequence(request)
except ValueError: pass
else: raise AssertionError('Non-finite F0 accepted')
print('PASS: adjacent frame endpoints, V6 pitch controller mapping and invalid F0')

request.pop('pitch_curve')
request['notes'] = [dict(position_ms=0, duration_ms=12000, tone=60, lyric='ni3')]
score = make_sequence(request)
assert score['tracks'][0]['parts'][0]['notes'][0]['phoneme'] == 'n i'
assert not score['masterTrack']['loop']['isEnabled']
assert score['masterTrack']['loop']['end'] > 12000*.96
print('PASS: pinyin request fallback and no fixed-loop truncation')

for velocity in (0,64,127):
    request['notes'][0]['velocity'] = velocity
    assert make_sequence(request)['tracks'][0]['parts'][0]['notes'][0]['velocity'] == velocity
for velocity in (-1,128,float('nan')):
    request['notes'][0]['velocity'] = velocity
    try: make_sequence(request)
    except ValueError: pass
    else: raise AssertionError('Invalid velocity accepted')
print('PASS: note velocity forwarding and validation')

request.pop('pitch_curve', None)
request['notes'] = [dict(position_ms=i*500, duration_ms=500, tone=60+i, lyric=lyric)
                    for i, lyric in enumerate(('qing', '-', '-'))]
slurs = make_sequence(request)['tracks'][0]['parts'][0]['notes']
assert [n['lyric'] for n in slurs] == ['qing', '-', '-']
assert [n['phoneme'] for n in slurs][1:] == ['-', '-']
assert slurs[0]['isProtected'] and all(not n['isProtected'] for n in slurs[1:])
for invalid in ([request['notes'][1]],
                [request['notes'][0], dict(position_ms=750, duration_ms=500, tone=62, lyric='-')]):
    request['notes'] = invalid
    try: make_sequence(request)
    except ValueError: pass
    else: raise AssertionError('Leading or disconnected slur accepted')
print('PASS: native slurs, chained slurs and leading/rest slur rejection')
