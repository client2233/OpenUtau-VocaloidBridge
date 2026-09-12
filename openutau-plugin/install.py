"""Install the managed settings command into stock OpenUtau's Plugins folder."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--data-dir', default=str(Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'OpenUtau'))
parser.add_argument('--project-dir', default=str(ROOT))
parser.add_argument('--python', default=sys.executable)
args=parser.parse_args()
project=Path(args.project_dir).expanduser().resolve()
if not (project/'enunu/configure.py').is_file(): raise ValueError('Bridge project not found')
dll=Path(__file__).parent/'bin/Release/net10.0/OpenUtau.Plugin.VocaloidBridge.dll'
if not dll.is_file(): raise ValueError('Build the plugin DLL first')
folder=Path(args.data_dir).expanduser().resolve()/'Plugins/VocaloidBridge'
folder.mkdir(parents=True,exist_ok=True)
settings=dict(LinuxPython=os.path.abspath(os.path.expanduser(args.python)),ProjectDirectory=str(project),
              BackendConfig=str(project/'bridge/config.local.json'),VoicesFile=str(project/'bridge/voices.local.json'))
files={dll.name:dll.read_bytes(),'bridge-launcher.json':(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode()}
for name, content in files.items():
    path=folder/name
    if path.exists() and path.read_bytes()!=content: shutil.copy2(path,path.with_name(name+'.previous'))
    temp=folder/(name+'.installing')
    temp.write_bytes(content);os.replace(temp,path)
print('Installed:',folder)
print('Restart OpenUtau, open a voice part, then External -> VOCALOID / Wine settings.')
