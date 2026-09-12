"""Verify the API path is explicit and local API code is not modified."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import subprocess
from host import invoke, windows_path
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);api=root/'API with spaces';(api/'v6api').mkdir(parents=True);(api/'v6api/__init__.py').touch()
    prefix=root/'prefix';prefix.mkdir();(prefix/'system.reg').touch()
    editor=root/'Editor';editor.mkdir()
    for name in ('VDM.dll','DSE.dll','VSM.dll'):(editor/name).touch()
    python=root/'python.exe';python.touch()
    config=root/'config.json';config.write_text(json.dumps(dict(api_dir=str(api),wine='/usr/bin/true',wine_prefix=str(prefix),windows_python=str(python),vocaloid_dir=str(editor),common_dir=str(root))))
    with patch('host.subprocess.run',return_value=subprocess.CompletedProcess([],0,'{"ok":true,"voices":[]}', '')) as run:
        invoke(config,'list');argv=run.call_args.args[0]
        assert argv[argv.index('--api-dir')+1]==windows_path(api)
        assert run.call_args.kwargs['env']['WINEPREFIX']==str(prefix)
    assert list((api/'v6api').iterdir())==[api/'v6api/__init__.py']
print('PASS: explicit user API directory is passed to our adapter without modifying or copying API files')
