"""Validate/save backend settings and translate file-picker paths for Wine."""
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import tempfile


def native_directory(value, prefix):
    path = PureWindowsPath(value)
    if path.drive.upper() == 'C:':
        return Path(prefix).expanduser().resolve() / 'drive_c' / Path(*path.parts[1:])
    if path.drive.upper() == 'Z:':
        return Path('/') / Path(*path.parts[1:])
    if path.drive:
        raise ValueError('目前支持 C:、Z: 或 Linux 绝对路径')
    return Path(value).expanduser().resolve()


def wine_directory(value, prefix):
    native = native_directory(value, prefix)
    drive = Path(prefix).expanduser().resolve() / 'drive_c'
    try:
        relative = native.relative_to(drive)
        return 'C:\\' + str(relative).replace('/', '\\')
    except ValueError:
        return 'Z:' + str(native).replace('/', '\\')


def validate(config):
    if not config.get('api_dir'):
        raise ValueError('请选择用户自行提供的 API 项目目录')
    api = Path(config['api_dir']).expanduser().resolve()
    if not (api/'v6api/__init__.py').is_file():
        raise ValueError('API 目录中应包含 v6api/__init__.py')
    prefix = Path(config['wine_prefix']).expanduser().resolve()
    if not (prefix / 'system.reg').is_file():
        raise ValueError('请选择已有 Wine 前缀（目录中应有 system.reg）')
    wine = shutil.which(config['wine'])
    if not wine:
        raise ValueError('找不到可执行的 Wine 程序')
    python = Path(config['windows_python']).expanduser().resolve()
    if not python.is_file():
        raise ValueError('找不到 Windows Python 可执行文件')
    timeout = int(config.get('timeout_seconds', 120))
    if not 1 <= timeout <= 3600:
        raise ValueError('超时应在 1–3600 秒之间')
    editor = native_directory(config['vocaloid_dir'], prefix)
    for name in ('VDM.dll', 'DSE.dll', 'VSM.dll'):
        if not (editor / name).is_file():
            raise ValueError(f'V6 编辑器目录中找不到 {name}')
    common = native_directory(config['common_dir'], prefix)
    if not common.is_dir():
        raise ValueError('找不到 V6 公共资源目录')
    return dict(api_dir=str(api),wine=str(Path(wine).resolve()), wine_prefix=str(prefix), windows_python=str(python),
                vocaloid_dir=wine_directory(config['vocaloid_dir'], prefix),
                common_dir=wine_directory(config['common_dir'], prefix), timeout_seconds=timeout)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', delete=False) as file:
            name = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write('\n')
        os.replace(name, path)
    finally:
        if name and os.path.exists(name): os.unlink(name)
