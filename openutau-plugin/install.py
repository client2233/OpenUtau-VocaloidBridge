"""Install the managed settings/renderer adapter into stock OpenUtau's Plugins folder."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from platform_support import IS_WINDOWS, data_directory
parser=argparse.ArgumentParser()
parser.add_argument('--data-dir', default=None if IS_WINDOWS else str(data_directory()))
parser.add_argument('--project-dir', default=str(ROOT))
parser.add_argument('--python', default=sys.executable)
parser.add_argument('--dll', help='Built plugin DLL (defaults to the most recently built Release DLL)')
args=parser.parse_args()
if not args.data_dir: parser.error('Windows 请用 --data-dir 指定 OpenUtau 实际用户数据目录（便携版通常是程序目录）')
project=Path(args.project_dir).expanduser().resolve()
if not (project/'enunu/configure.py').is_file(): raise ValueError('Bridge project not found')
candidates=list((Path(__file__).parent/'bin/Release').glob('net*/OpenUtau.Plugin.VocaloidBridge.dll'))
dll=Path(args.dll) if args.dll else max(candidates, key=lambda p:p.stat().st_mtime, default=Path('missing-plugin.dll'))
if not dll.is_file(): raise ValueError('Build the plugin DLL first')
folder=Path(args.data_dir).expanduser().resolve()/'Plugins/VocaloidBridge'
folder.mkdir(parents=True,exist_ok=True)
settings=dict(Python=os.path.abspath(os.path.expanduser(args.python)),ProjectDirectory=str(project),
              BackendConfig=str(project/'bridge/config.local.json'),VoicesFile=str(project/'bridge/voices.local.json'))
files={dll.name:dll.read_bytes(),'bridge-launcher.json':(json.dumps(settings,ensure_ascii=False,indent=2)+'\n').encode()}
for name, content in files.items():
    path=folder/name
    if path.exists() and path.read_bytes()!=content: shutil.copy2(path,path.with_name(name+'.previous'))
    temp=folder/(name+'.installing')
    temp.write_bytes(content);os.replace(temp,path)
print('Installed:',folder)
print('Restart OpenUtau, open a voice part, then External -> VOCALOID / ' + ('Windows' if IS_WINDOWS else 'Wine') + ' settings.')
