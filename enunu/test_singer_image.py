"""Check picture installation and preservation when upgrading descriptors."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from singer_image import set_image, import_installed_images

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    voices = root / 'voices.json'
    voices.write_text(json.dumps({'voices': [{'name': 'Test', 'comp_id': 'test', 'lang_id': 4}]}))
    command = [sys.executable, str(Path(__file__).with_name('prepare_singers.py')), '--voices', str(voices), '--data-dir', tmp]
    subprocess.run(command, check=True, capture_output=True)
    picture = root / 'picture.png'
    picture.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
    folder = set_image(tmp, 'Test', picture)
    metadata = (folder / 'character.yaml').read_text()
    assert 'image: "bridge-avatar.png"' in metadata
    assert 'portrait: "bridge-avatar.png"' in metadata
    assert (folder / 'bridge-avatar.png').read_bytes() == picture.read_bytes()
    subprocess.run(command + ['--update'], check=True, capture_output=True)
    assert (folder / 'character.yaml').read_text() == metadata
    try:
        set_image(tmp, '../invalid', picture)
        raise AssertionError('Unsafe name accepted')
    except ValueError:
        pass
    (folder / 'character.yaml').write_text('name: Test\nsinger_type: enunu\n')
    installed = root / 'prefix/drive_c/Program Files/Test/Common/Voicelib/test'
    installed.mkdir(parents=True)
    (installed / 'setup.bmp').write_bytes(b'BM' + bytes(52))
    config = {'wine_prefix': str(root/'prefix'), 'common_dir': 'C:\\Common'}
    assert import_installed_images(tmp, [{'name':'Test','comp_id':'test'}], config) == 1
    assert 'bridge-avatar.bmp' in (folder/'character.yaml').read_text()
    assert 'portrait:' not in (folder/'character.yaml').read_text()
    with (folder/'character.yaml').open('a') as metadata:
        metadata.write('portrait: "bridge-avatar.bmp"\n')
    assert import_installed_images(tmp, [{'name':'Test','comp_id':'test'}], config) == 1
    assert 'portrait:' not in (folder/'character.yaml').read_text()
    with (folder/'character.yaml').open('a') as metadata:
        metadata.write('portrait: "custom.png"\n')
    assert import_installed_images(tmp, [{'name':'Test','comp_id':'test'}], config) == 0
    assert 'portrait: "custom.png"' in (folder/'character.yaml').read_text()
print('PASS: native image/portrait metadata, copied picture, descriptor updates preserve settings')
