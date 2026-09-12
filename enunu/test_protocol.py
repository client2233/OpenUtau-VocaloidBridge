import json
from pathlib import Path
import tempfile
import numpy as np
from server import score, acoustic

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    (root/'bridge.voice.json').write_text(json.dumps(dict(comp_id='test', lang_id=4)))
    ust = root/'test.ust'
    def write(tempo, lyric='la'):
        ust.write_text(f'[#SETTING]\nTempo={tempo}\nVoiceDir={root}\n[#0000]\nLength=240\nLyric=R\nNoteNum=60\n[#0001]\nLength=480\nLyric={lyric}\nNoteNum=60\n[#TRACKEND]\n',encoding='shift_jis')
    for tempo in (60,120,180):
        write(tempo)
        voice, notes, segments, duration = score(ust)
        assert abs(notes[0]['position_ms'] - 30000/tempo) < 1e-6
        assert abs(notes[0]['duration_ms'] - 60000/tempo) < 1e-6
        result = acoustic(ust)
        f0 = np.load(result['path_f0'])
        assert len(f0) == round(duration/5)
        assert np.all(f0[:round(notes[0]['position_ms']/5)] == 0)
        assert abs(f0[-1] - 261.625565) < .001
    for lyric in ('ni3','hao3','shi','xue','user_alias'):
        write(120,lyric)
        note=score(ust)[1][0]
        assert note['lyric']==lyric and 'phoneme' not in note
print('PASS: UST timing, rests and F0; lyrics forwarded without engine phoneme conversion')
