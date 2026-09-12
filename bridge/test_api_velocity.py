"""Optional real-backend velocity probe; requires the user's configured API/Wine.
Run: python3 bridge/test_api_velocity.py [config.json]
Reports differences against a repeated baseline; differing PCM alone is not proof
of a useful consonant-speed change. Creates only temporary files.
"""
import json
from pathlib import Path
import sys
import tempfile
import wave
import numpy as np
from host import invoke

config = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('config.local.json')
voice = next(v for v in invoke(config, 'list')['voices'] if v['lang_id'] == 4)
with tempfile.TemporaryDirectory(prefix='velocity-probe-') as folder:
    root = Path(folder)
    arrays = []
    for velocity in (64, 64, 0, 127):
        request = dict(protocol=1, comp_id=voice['comp_id'], lang_id=4,
            notes=[dict(position_ms=250, duration_ms=1000, tone=60, lyric='ka', velocity=velocity)])
        path = root/'request.json'; path.write_text(json.dumps(request))
        output = root/'result.wav'; invoke(config, 'render', path, output)
        with wave.open(str(output)) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (44100, 1, 2)
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)
        assert np.max(np.abs(pcm)) > 300
        arrays.append(pcm)
    for label, pcm in zip(('repeat64', 'velocity0', 'velocity127'), arrays[1:]):
        n = min(len(arrays[0]), len(pcm))
        diff = pcm[:n] - arrays[0][:n]
        print(label, 'RMS difference:', float(np.sqrt(np.mean(diff**2))),
              'maximum difference:', float(np.max(np.abs(diff))))
print('PASS: velocity requests accepted; listen/inspect consonant timing to verify the effect')
