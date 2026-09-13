"""User-supplied singer pictures through native OpenUtau metadata."""
import json
from pathlib import Path
import os

def set_image(data_dir, name, source):
    if not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('Invalid singer name')
    folder = Path(data_dir).expanduser().resolve() / 'Singers' / ('VOCALOID-Wine-' + name)
    metadata = folder / 'character.yaml'
    if not metadata.is_file():
        raise ValueError('请先安装声库描述')
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in ('.png', '.jpg', '.jpeg', '.bmp'):
        raise ValueError('请选择 PNG、JPEG 或 BMP 图片')
    content = source.read_bytes()
    if not (content.startswith(b'\x89PNG\r\n\x1a\n') or content.startswith(b'\xff\xd8\xff') or content.startswith(b'BM')):
        raise ValueError('图片文件格式无效')
    image = 'bridge-avatar' + suffix
    temp = folder / (image + '.installing')
    temp.write_bytes(content)
    os.replace(temp, folder / image)
    lines = metadata.read_text(encoding='utf-8').splitlines()
    lines = [line for line in lines if not line.startswith(('image:', 'portrait:'))]
    text = '\n'.join(lines) + '\nimage: ' + json.dumps(image) + '\nportrait: ' + json.dumps(image) + '\n'
    temp = metadata.with_name('character.yaml.installing')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, metadata)
    return folder


def import_installed_images(data_dir, voices, config):
    """Match local installation pictures by exact voice ID; never download assets."""
    from settings import native_directory
    prefix = Path(config['wine_prefix']).expanduser().resolve()
    roots = [native_directory(config['common_dir'], prefix)]
    roots += [prefix / 'drive_c' / name for name in ('Program Files', 'Program Files (x86)')]
    ids = {voice['comp_id'] for voice in voices}
    pictures = {}
    for root in roots:
        if not root.is_dir(): continue
        for image in root.rglob('setup.bmp'):
            if image.parent.name in ids:
                pictures.setdefault(image.parent.name, image)
    count = 0
    for voice in voices:
        image = pictures.get(voice['comp_id'])
        if image is None: continue
        name = voice['name']
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            raise ValueError('Invalid singer name')
        metadata = Path(data_dir).expanduser().resolve() / 'Singers' / ('VOCALOID-Wine-' + name) / 'character.yaml'
        if not metadata.is_file(): continue
        if any(line.startswith('image:') for line in metadata.read_text(encoding='utf-8').splitlines()):
            continue # Keep user-selected pictures.
        set_image(data_dir, name, image)
        count += 1
    return count
