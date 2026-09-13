"""Verify DLL discovery using the installed, unmodified OpenUtau Core.
Run: python3 openutau-plugin/test_launch.py [path/to/dotnet]
Requires built openutau-plugin and Smoke projects.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='utau-plugin-test-') as folder:
    temp=Path(folder);data=temp/'data';plugin=data/'OpenUtau/Plugins/VocaloidBridge'
    project=temp/'project with spaces';(project/'enunu').mkdir(parents=True);(project/'enunu/configure.py').touch()
    log=temp/'argv.json';python=temp/'fake python'
    python.write_text('#!/usr/bin/python3\nimport json,sys\nfrom pathlib import Path\nPath('+repr(str(log))+').write_text(json.dumps(sys.argv[1:]))\n')
    python.chmod(0o755)
    alias=temp/'venv/python';alias.parent.mkdir();alias.symlink_to(python)
    subprocess.run([sys.executable,str(root/'openutau-plugin/install.py'),
        '--data-dir',str(data/'OpenUtau'),'--project-dir',str(project),'--python',str(alias)],check=True,capture_output=True,text=True)
    launcher=json.loads((plugin/'bridge-launcher.json').read_text())
    assert launcher['Python']==str(alias), 'Installer dereferenced the virtualenv interpreter'
    env=dict(os.environ,XDG_DATA_HOME=str(data),XDG_CACHE_HOME=str(temp/'cache'))
    result=subprocess.run([sys.argv[1] if len(sys.argv)>1 else 'dotnet',
        str(root/'openutau-plugin/Smoke/bin/Release/net10.0/Smoke.dll'),str(log)],env=env,text=True,capture_output=True,timeout=20)
    print(result.stdout,end='')
    if result.returncode: print(result.stderr,file=sys.stderr)
    raise SystemExit(result.returncode)
