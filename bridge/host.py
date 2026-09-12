"""Native Linux launcher. No shell interpolation; configurable Wine prefix."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def windows_path(path):
    # The default Wine Z: mapping exposes the Linux filesystem.
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


def invoke(config_path, command, request=None, output=None):
    from settings import validate
    config = validate(json.loads(Path(config_path).read_text(encoding='utf-8')))
    prefix = Path(config['wine_prefix']).expanduser().resolve()
    if not (prefix / 'system.reg').is_file():
        raise ValueError('Select an existing Wine prefix')
    python = Path(config['windows_python']).expanduser().resolve()
    if not python.is_file():
        raise ValueError('Windows Python executable not found')
    worker = Path(__file__).with_name('worker.py')
    argv = [config.get('wine', 'wine'), str(python), windows_path(worker), command,
            '--api-dir', windows_path(config['api_dir']), '--vocaloid-dir', config['vocaloid_dir'], '--common-dir', config['common_dir']]
    if command == 'render':
        if not request or not output:
            raise ValueError('Render requires request and output paths')
        argv += ['--request', windows_path(request), '--output', windows_path(output)]
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG='-all')
    result = subprocess.run(argv, env=env, capture_output=True, text=True,
                            timeout=config.get('timeout_seconds', 120))
    if result.stderr:
        print(result.stderr, file=sys.stderr, end='')
    lines = result.stdout.strip().splitlines()
    if not lines:
        raise RuntimeError(f'Wine worker exited {result.returncode} without a reply')
    reply = json.loads(lines[-1])
    if result.returncode != 0 or not reply.get('ok'):
        raise RuntimeError(reply.get('error', f'Worker exited {result.returncode}'))
    if command == 'list':
        from pinyin import aliases
        reply['lyrics'] = aliases()
    return reply


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['list', 'render'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--request')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        print(json.dumps(invoke(args.config, args.command, args.request, args.output)))
    except Exception as error:
        print(json.dumps(dict(ok=False, error=str(error))))
        sys.exit(1)
