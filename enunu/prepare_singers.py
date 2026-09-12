"""Install plain ENUNU singer descriptors, without OpenUtau source patches."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from pinyin import aliases

parser = argparse.ArgumentParser()
parser.add_argument('--voices', required=True)
parser.add_argument('--data-dir', required=True, help='OpenUtau data directory')
parser.add_argument('--update', action='store_true', help='Upgrade only recognized original prototype tables, with backups')
args = parser.parse_args()
old_tables = {
    'lyrics.table': '\n'.join(f'{x} {x}' for x in ('la', 'a', 'i', 'u', 'e', 'o')) + '\n',
    'phonemes.hed': 'QS "phonemes" {*-la+*,*-a+*,*-i+*,*-u+*,*-e+*,*-o+*}\n',
}
lyrics = aliases()
root = Path(args.data_dir).expanduser().resolve() / 'Singers'
voices = json.loads(Path(args.voices).read_text(encoding='utf-8'))['voices']
for voice in voices:
    name = voice['name']
    if not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('Invalid singer name')
    folder = root / ('VOCALOID-Wine-' + name)
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        'character.txt': '',
        'character.yaml': 'name: ' + json.dumps(name) + '\nsinger_type: enunu\ntext_file_encoding: utf-8\n',
        'enuconfig.yaml': 'feature_type: melf0\nsample_rate: 44100\nframe_period: 5.0\ntable_path: lyrics.table\nquestion_path: phonemes.hed\nextensions:\n  wav_synthesizer: synthe\n',
        'bridge.voice.json': json.dumps(voice, ensure_ascii=False, indent=2) + '\n',
        'lyrics.table': '\n'.join(f'{x} {x}' for x in lyrics) + '\n',
        'phonemes.hed': 'QS "phonemes" {' + ','.join(f'*-{x}+*' for x in lyrics) + '}\n',
    }
    for name, content in files.items():
        path = folder / name
        if path.exists():
            current = path.read_text(encoding='utf-8')
            if current != content:
                if not args.update or current != old_tables.get(name):
                    raise ValueError(f'Existing descriptor differs, refusing overwrite: {path}')
                backup = path.with_name(path.name + '.before-pinyin')
                if not backup.exists(): backup.write_text(current, encoding='utf-8')
                path.write_text(content, encoding='utf-8')
        else:
            path.write_text(content, encoding='utf-8')
    print(folder)
print('Rescan singers/restart OpenUtau. Select ENUNU renderer and Default phonemizer.')
