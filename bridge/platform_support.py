"""Small native-platform helpers; Linux continues to use Wine."""
import os
from pathlib import Path
import subprocess

IS_WINDOWS = os.name == 'nt'


def data_directory():
    if IS_WINDOWS:
        return Path.home() / 'Documents/OpenUtau'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'OpenUtau'


def process_alive(pid):
    if pid <= 0: return False
    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle: return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally: kernel.CloseHandle(handle)
    try: os.kill(pid, 0)
    except ProcessLookupError: return False
    except PermissionError: return True
    return True


def stop_tree(process, force=False):
    if process.poll() is not None: return
    if IS_WINDOWS:
        # Kill only the service we started and its children, never all Python processes.
        subprocess.Popen(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        try: os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError: pass


def lock_window(file):
    if IS_WINDOWS:
        import msvcrt
        file.seek(0)
        if not file.read(1):
            file.write(b'0'); file.flush()
        file.seek(0)
        try: msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error: raise BlockingIOError('Settings window already open') from error
    else:
        import fcntl
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
