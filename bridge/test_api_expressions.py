"""Optional real-backend probe: python3 bridge/test_api_expressions.py [config.json].
Requires user-provided API/Wine/editor/voicebanks. Prints PCM differences against
an identical baseline; a difference proves an effect, not identical UI semantics.
All generated requests/audio remain temporary; external API files are untouched.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import wave
import numpy as np
from host import invoke

config = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('config.local.json')
voice = next(v for v in invoke(config, 'list')['voices'] if v['lang_id'] == 4)
base = dict(protocol=1, comp_id=voice['comp_id'], lang_id=4,
    notes=[dict(position_ms=250, duration_ms=700, tone=60, lyric='shi'),
           dict(position_ms=950, duration_ms=700, tone=67, lyric='a')])
with tempfile.TemporaryDirectory(prefix='expression-probe-') as folder:
    root = Path(folder)
    def render(request):
        path = root/'request.json'; path.write_text(json.dumps(request))
        output = root/'result.wav'; invoke(config, 'render', path, output)
        with wave.open(str(output)) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (44100, 1, 2)
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)
    baseline = render(base)
    def compare(label, request):
        pcm = render(request)
        n = min(len(pcm), len(baseline)); diff = pcm[:n] - baseline[:n]
        print(label, 'RMS difference:', round(float(np.sqrt(np.mean(diff**2))), 4),
              'max:', int(np.max(np.abs(diff))), flush=True)
    compare('identical baseline', base)
    for name, value in [('brightness', 127), ('breathiness', 100),
                        ('character', -32), ('clearness', 100), ('growl', 100),
                        ('portamento', 127), ('dynamics', 0), ('air', 100), ('exciter', 32)]:
        request = copy.deepcopy(base)
        request['controller_curves'] = {name: dict(frame_period_ms=5, values=[value])}
        compare(name, request)
    for name, value in [('opening', 0), ('accent', 100), ('decay', 100)]:
        request = copy.deepcopy(base)
        for note in request['notes']: note['expressions'] = {name: value}
        compare(name, request)
print('PASS: all tested controller/note-expression requests accepted')
