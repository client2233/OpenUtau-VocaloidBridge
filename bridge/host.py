"""Native Linux launcher. No shell interpolation; configurable Wine prefix."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import queue
import threading
import tempfile


def windows_path(path):
    # The default Wine Z: mapping exposes the Linux filesystem.
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


_persistent = False
_worker = None


def enable_persistent():
    global _persistent
    _persistent = True


def close_worker():
    global _worker
    if _worker is not None:
        _worker.close()
        _worker = None


class Worker:
    def __init__(self, argv, env):
        self.log = tempfile.TemporaryFile(mode='w+t')
        self.replies = queue.Queue()
        try:
            self.process = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1)
        except Exception:
            self.log.close()
            raise
        def read():
            try:
                for line in self.process.stdout:
                    try: reply = json.loads(line)
                    except json.JSONDecodeError: continue
                    if isinstance(reply, dict) and 'ok' in reply: self.replies.put(reply)
            finally: self.replies.put(None)
        threading.Thread(target=read, daemon=True).start()

    def render(self, request, output, timeout):
        self.process.stdin.write(json.dumps(dict(request=windows_path(request), output=windows_path(output))) + '\n')
        self.process.stdin.flush()
        try: reply = self.replies.get(timeout=timeout)
        except queue.Empty: raise TimeoutError('Wine worker render timed out')
        if reply is None:
            self.log.seek(0)
            raise RuntimeError('Wine worker exited: ' + self.log.read()[-2000:])
        if not reply.get('ok'): raise RuntimeError(reply.get('error', 'Render failed'))
        return reply

    def close(self):
        try:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"command":"shutdown"}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    self.process.kill()
                    self.process.wait(timeout=3)
        finally:
            self.process.stdin.close()
            self.process.stdout.close()
            self.log.close()


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
    if _persistent and command == 'render':
        global _worker
        signature = json.dumps(config, sort_keys=True)
        if _worker is not None and _worker.signature != signature: close_worker()
        if _worker is None:
            worker_argv = argv[:3] + ['serve'] + argv[4:]
            worker_argv = worker_argv[:worker_argv.index('--request')]
            _worker = Worker(worker_argv, env)
            _worker.signature = signature
        try:
            return _worker.render(request, output, config.get('timeout_seconds', 120))
        except Exception:
            close_worker()
            raise
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
