"""Run: python3 bridge/test_settings.py"""
import json
from pathlib import Path
import tempfile
from settings import native_directory, save_json, validate, wine_directory

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder); prefix=root/'prefix with spaces'; prefix.mkdir()
    (prefix/'system.reg').write_text('test')
    editor=prefix/'drive_c/Program Files/VOCALOID6/Editor'; editor.mkdir(parents=True)
    for name in ('VDM.dll','DSE.dll','VSM.dll'): (editor/name).touch()
    common=prefix/'drive_c/Program Files/Common Files/VOCALOID6'; common.mkdir(parents=True)
    python=root/'python.exe'; python.touch()
    api=root/'user API';(api/'v6api').mkdir(parents=True);(api/'v6api/__init__.py').touch()
    config=dict(api_dir=str(api),wine='/usr/bin/true', wine_prefix=str(prefix),windows_python=str(python),
                vocaloid_dir=str(editor),common_dir=str(common),timeout_seconds='120')
    value=validate(config)
    assert native_directory(value['vocaloid_dir'],prefix)==editor
    assert native_directory(wine_directory(str(root),prefix),prefix)==root
    assert native_directory(r'C:\Program Files\VOCALOID6\Editor',prefix)==editor
    path=root/'settings.json'; save_json(path,value)
    assert json.loads(path.read_text())==value
    for key, invalid in [('api_dir',str(root)),('wine','/missing/wine'),('wine_prefix',str(root)),
                         ('windows_python',str(root/'missing.exe')),('timeout_seconds','0'),
                         ('vocaloid_dir',str(root)),('common_dir',str(root/'missing'))]:
        bad=dict(config);bad[key]=invalid
        try: validate(bad)
        except ValueError: pass
        else: raise AssertionError(f'Invalid {key} accepted')
    (editor/'VSM.dll').unlink()
    try: validate(config)
    except ValueError: pass
    else: raise AssertionError('Missing VSM accepted')
print('PASS: Linux/C:/Z: directory round trips, atomic save, invalid paths/timeout/DLL rejection')
