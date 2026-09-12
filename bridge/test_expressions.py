"""Run: python3 bridge/test_expressions.py (no API/Wine required)."""
from worker import make_sequence

request = dict(comp_id='user-selected-voice', lang_id=4,
    notes=[dict(position_ms=250, duration_ms=500, tone=60, lyric='ni3', velocity=83,
                expressions=dict(opening=95, accent=20, decay=80))],
    pitch_curve=dict(frame_period_ms=5, f0=[0]*50+[261.625565]*100))
for name in ('brightness', 'breathiness', 'clearness', 'growl', 'portamento', 'dynamics'):
    request['controller_curves'] = {name: dict(frame_period_ms=5, values=[0,0,64,64,127])}
    part = make_sequence(request)['tracks'][0]['parts'][0]
    assert [c['name'] for c in part['controllers'][:2]] == ['pitchBendSens', 'pitchBend']
    assert part['controllers'][-1] == dict(name=name, events=[dict(pos=0,value=0),dict(pos=10,value=64),dict(pos=19,value=127)])
    assert part['notes'][0]['velocity'] == 83
    assert part['notes'][0]['exp']['opening'] == 95
    assert part['notes'][0]['exp']['accent'] == 20 and part['notes'][0]['exp']['decay'] == 80
for value in (-1,128,float('nan'),float('inf')):
    request['controller_curves'] = {'brightness': dict(frame_period_ms=5, values=[value])}
    try: make_sequence(request)
    except ValueError: pass
    else: raise AssertionError('Invalid controller accepted')
request['controller_curves'] = {'not-supported':dict(frame_period_ms=5,values=[64])}
try: make_sequence(request)
except ValueError: pass
else: raise AssertionError('Unknown controller accepted')
request['controller_curves'] = {}
for key in ('opening','accent','decay'):
    request['notes'][0]['expressions'] = {key:128}
    try: make_sequence(request)
    except ValueError: pass
    else: raise AssertionError('Invalid note expression accepted')
for name in ('character','exciter'):
    request['notes'][0]['expressions'] = {}
    request['controller_curves'] = {name:dict(frame_period_ms=5,values=[-64,0,63])}
    assert make_sequence(request)['tracks'][0]['parts'][0]['controllers'][-1]['events'][0]['value'] == -64
print('PASS: all expression mappings, curve compression, pitch preservation and invalid-input rejection')

request['controller_curves'] = {}
request['notes'][0]['expressions'] = {}
request['pitch_curve'] = dict(frame_period_ms=5, f0=[293.664768]*2, sensitivity=[6,12])
request['notes'][0]['position_ms'] = 0
part = make_sequence(request)['tracks'][0]['parts'][0]
assert part['controllers'][0]['events'] == [dict(pos=0,value=6),dict(pos=5,value=12)]
assert [e['value'] for e in part['controllers'][1]['events']] == [round(2/6*8192), round(2/12*8192)]
request['pitch_curve']['sensitivity'] = [0,0]
try: make_sequence(request)
except ValueError: pass
else: raise AssertionError('PBS 0 accepted nonzero pitch deviation')
print('PASS: variable PBS preserves absolute F0 and rejects unrepresentable pitch')
