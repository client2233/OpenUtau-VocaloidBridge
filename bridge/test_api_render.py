"""Optional real-backend check: python3 bridge/test_api_render.py [config.json].
Requires the user's API, Wine, Windows Python and licensed editor/voicebanks.
Creates only temporary request/audio files; does not edit the external API.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import wave
import numpy as np
from host import invoke

config = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('config.local.json')
api = Path(json.loads(config.read_text())['api_dir']).expanduser().resolve()
files = list((api/'v6api').rglob('*.py'))
def hashes():
    return {str(p): hashlib.sha256(p.read_bytes()).digest() for p in files}
before = hashes()
voices = [v for v in invoke(config, 'list')['voices'] if v['lang_id'] == 4]
assert voices, 'No traditional Chinese voicebanks available'
with tempfile.TemporaryDirectory(prefix='api-render-check-') as folder:
    root = Path(folder)
    for voice in voices:
        request = dict(protocol=1, comp_id=voice['comp_id'], lang_id=4,
            notes=[dict(position_ms=250, duration_ms=500, tone=60, lyric='ni3'),
                   dict(position_ms=750, duration_ms=500, tone=62, lyric='hao3')],
            pitch_curve=dict(frame_period_ms=5, f0=[0]*50+[261.625565]*100+[293.664768]*100+[0]*100))
        path = root/'request.json'; path.write_text(json.dumps(request))
        output = root/'result.wav'; invoke(config, 'render', path, output)
        with wave.open(str(output)) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (44100, 1, 2)
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)
            assert np.max(np.abs(pcm)) > 300, voice['name']
        print('PASS:', voice['name'], 'real pinyin/F0 render')
assert hashes() == before, 'External API files changed'
print('PASS: external API source unchanged')
