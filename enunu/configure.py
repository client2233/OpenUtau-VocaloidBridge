"""Standalone native settings/launcher for the existing OpenUtau ENUNU bridge."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge'))
from host import invoke
from settings import native_directory, save_json, validate


class SettingsWindow:
    def __init__(self, root, config, voices, data_dir, parent_pid=None):
        self.root, self.config, self.voices = root, Path(config), Path(voices)
        self.events = queue.Queue()
        self.process = None
        self.busy = False
        self.parent_pid = parent_pid
        self.stopping = False
        self.closing = False
        root.title('VOCALOID · OpenUtau 桥接设置')
        root.geometry('830x660')
        root.minsize(720, 570)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='VOCALOID / Wine', font=('', 15, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
        initial = json.loads(self.config.read_text()) if self.config.exists() else {
            'api_dir':'', 'wine':'/usr/bin/wine', 'wine_prefix':str(Path.home()/'.wine'),
            'windows_python':'', 'vocaloid_dir':'', 'common_dir':'', 'timeout_seconds':120}
        self.fields = {}
        self.controls = []
        rows = [('api_dir', 'API 项目目录（用户提供）', True), ('wine', 'Wine 程序', False),
                ('wine_prefix', 'Wine 前缀', True), ('windows_python', 'Windows Python', False),
                ('vocaloid_dir', 'V6 编辑器 / DLL 目录', True), ('common_dir', 'V6 公共资源目录', True),
                ('timeout_seconds', '单次合成超时（秒）', None), ('data_dir', 'OpenUtau 用户数据目录', True)]
        initial['data_dir'] = str(data_dir or initial.get('openutau_data_dir', Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'OpenUtau'))
        for row, (key, label, directory) in enumerate(rows, 1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10), pady=4)
            value = initial.get(key, '')
            variable = tk.StringVar(value=str(value))
            self.fields[key] = variable
            entry = ttk.Entry(frame, textvariable=variable)
            entry.grid(row=row, column=1, sticky='ew', pady=4)
            self.controls.append(entry)
            if directory is not None:
                button = ttk.Button(frame, text='选择…', command=lambda k=key, d=directory: self.choose(k,d))
                button.grid(row=row, column=2, padx=(8,0), pady=4)
                self.controls.append(button)
        actions = ttk.Frame(frame)
        actions.grid(row=9, column=0, columnspan=3, sticky='w', pady=(12,8))
        for label, command in [('保存设置', self.save), ('刷新外部声库', self.refresh), ('安装 / 更新声库描述', self.install)]:
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side='left', padx=(0,8)); self.controls.append(button)
        self.voice_list = tk.Listbox(frame, height=4)
        self.voice_list.grid(row=10,column=0,columnspan=3,sticky='ew')
        if self.voices.exists(): self.show_voices(json.loads(self.voices.read_text()).get('voices', []))
        service = ttk.Frame(frame)
        service.grid(row=11,column=0,columnspan=3,sticky='w',pady=10)
        self.start_button = ttk.Button(service,text='启动桥接',command=self.start)
        self.start_button.pack(side='left',padx=(0,8))
        self.stop_button = ttk.Button(service,text='停止桥接',command=self.stop,state='disabled')
        self.stop_button.pack(side='left',padx=(0,12))
        self.status = tk.StringVar(value='桥接未启动')
        ttk.Label(service,textvariable=self.status).pack(side='left')
        ttk.Label(frame,text='在 OpenUtau 选择外部声库、ENUNU 渲染器和 Default 音素器。\n更换后端后，重启 OpenUtau 并清除测试项目音频缓存；插件模式下关闭窗口会隐藏到后台；再次点击插件菜单可打开。').grid(row=12,column=0,columnspan=3,sticky='w',pady=(0,8))
        self.log = ScrolledText(frame,height=8,state='disabled',wrap='word')
        self.log.grid(row=13,column=0,columnspan=3,sticky='nsew')
        frame.rowconfigure(13,weight=1)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)

    def choose(self,key,directory):
        try:
            current = self.fields[key].get()
            if key in ('vocaloid_dir','common_dir'):
                current = str(native_directory(current,self.fields['wine_prefix'].get()))
            initial = Path(current).expanduser()
            if not initial.is_dir(): initial = initial.parent
            options = dict(parent=self.root,initialdir=str(initial),title='选择目录' if directory else '选择文件')
            value = filedialog.askdirectory(**options) if directory else filedialog.askopenfilename(**options)
            if value: self.fields[key].set(value)
        except Exception as error: self.error(error)

    def error(self,error):
        self.write_log(str(error)); messagebox.showerror('桥接设置',str(error),parent=self.root)

    def write_log(self,text):
        self.log.configure(state='normal'); self.log.insert('end',text.rstrip()+'\n')
        if int(self.log.index('end-1c').split('.')[0]) > 500: self.log.delete('1.0','100.0')
        self.log.see('end'); self.log.configure(state='disabled')

    def save(self):
        try:
            values = {key:value.get() for key,value in self.fields.items() if key != 'data_dir'}
            config = validate(values)
            if not self.fields['data_dir'].get().strip():
                raise ValueError('请选择 OpenUtau 用户数据目录')
            config['openutau_data_dir'] = str(Path(self.fields['data_dir'].get()).expanduser().resolve())
            save_json(self.config,config)
            for key,value in config.items():
                if key in self.fields: self.fields[key].set(json.dumps(value,ensure_ascii=False) if key=='backend_args' else str(value))
            self.write_log('设置已保存：'+str(self.config))
            return True
        except Exception as error: self.error(error); return False

    def show_voices(self,voices):
        self.voice_list.delete(0,'end')
        for voice in voices:
            self.voice_list.insert('end',voice['name']+'   '+voice['comp_id'])

    def background(self,work,done):
        self.busy = True; self.set_controls()
        def run():
            try: self.events.put(('done',done,work()))
            except Exception as error: self.events.put(('error',error))
        threading.Thread(target=run,daemon=True).start()

    def refresh(self):
        if not self.save(): return
        self.status.set('正在读取声库…')
        def work():
            return self.read_voices()
        def done(voices):
            self.show_voices(voices); self.status.set('已读取 '+str(len(voices))+' 个中文声库')
            self.write_log('声库列表已更新。点击“安装 / 更新声库描述”后重启 OpenUtau。')
        self.background(work,done)

    def read_voices(self):
        result = invoke(self.config,'list')
        voices = result['voices']
        if not voices: raise ValueError('该前缀中没有可用的外部声库')
        result['voices'] = voices
        save_json(self.voices,result)
        return voices

    def install(self):
        if not self.save(): return
        data = Path(self.fields['data_dir'].get()).expanduser().resolve()
        def work():
            voices = self.read_voices()
            result = subprocess.run([sys.executable,str(ROOT/'enunu/prepare_singers.py'),
                '--voices',str(self.voices),'--data-dir',str(data),'--update'],capture_output=True,text=True,timeout=30)
            if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip())
            return result.stdout, voices
        def done(result):
            output, voices = result
            self.show_voices(voices)
            self.write_log(output); self.status.set('声库描述已安装，请重启 OpenUtau')
        self.background(work,done)

    def start(self):
        if self.process is not None: return
        try:
            for port in (15556,15555):
                with socket.socket() as probe:
                    # Match ZeroMQ: closed connections in TIME_WAIT are reusable.
                    probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                    probe.bind(('127.0.0.1',port))
            if not self.save(): return
            self.process = subprocess.Popen([sys.executable,str(ROOT/'enunu/server.py'),
                '--config',str(self.config)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,bufsize=1,start_new_session=True)
            save_json(str(self.config)+'.service.local.json',dict(Ready=False,Pid=self.process.pid))
            self.status.set('正在启动桥接…'); self.set_controls()
            process = self.process
            def read():
                try:
                    for line in process.stdout:
                        self.events.put(('log',line))
                finally:
                    process.stdout.close()
            threading.Thread(target=read,daemon=True).start()
        except OSError as error:
            if error.errno == 98: self.error(f'端口 {port} 已被其他服务占用，请先停止原来的 ENUNU / 桥接服务')
            else: self.error(error)

    def stop(self):
        if self.process and self.process.poll() is None:
            save_json(str(self.config)+'.service.local.json',dict(Ready=False,Pid=self.process.pid))
            self.stopping = True
            self.status.set('正在停止桥接…')
            try: os.killpg(self.process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            self.stop_button.configure(state='disabled')
            process = self.process
            def force_stop():
                if process.poll() is None:
                    try: os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
            self.root.after(2000,force_stop)

    def set_controls(self):
        running = self.process is not None
        state = 'disabled' if running or self.busy else 'normal'
        for control in self.controls: control.configure(state=state)
        self.start_button.configure(state=state)
        self.stop_button.configure(state='normal' if running and not self.stopping else 'disabled')

    def poll(self):
        if self.parent_pid and not self.closing:
            try: os.kill(self.parent_pid, 0)
            except ProcessLookupError:
                self.closing = True
                self.stop()
        while True:
            try: event = self.events.get_nowait()
            except queue.Empty: break
            if event[0] == 'log':
                self.write_log(event[1])
                if 'ENUNU VOCALOID bridge ready' in event[1] and not self.stopping and self.process and self.process.poll() is None:
                    self.status.set('桥接已启动 · 15555 / 15556')
                    save_json(str(self.config)+'.service.local.json',dict(Ready=True,Pid=self.process.pid))
            else:
                self.busy = False; self.set_controls()
                if event[0] == 'done': event[1](event[2])
                else: self.status.set('操作失败'); self.error(event[1])
        if self.process and self.process.poll() is not None:
            save_json(str(self.config)+'.service.local.json',dict(Ready=False,Pid=self.process.pid))
            code = self.process.returncode
            # A backend can retain this pipe after the server exits. Closing it
            # here waits for the reader lock and freezes Tk; the reader owns it.
            self.process = None
            self.status.set('桥接已停止' if self.stopping else f'桥接已退出（{code}），请查看日志')
            self.stopping = False; self.set_controls()
        if self.closing and self.process is None and not self.busy:
            self.root.destroy(); return
        self.root.after(100,self.poll)

    def close(self):
        if self.parent_pid:
            self.root.withdraw()
            return
        if self.busy:
            messagebox.showinfo('桥接设置','请等待当前操作完成后关闭窗口',parent=self.root); return
        self.closing = True
        if self.process: self.stop()
        else: self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',default=str(ROOT/'bridge/config.local.json'))
    parser.add_argument('--voices',default=str(ROOT/'bridge/voices.local.json'))
    parser.add_argument('--data-dir',help='OpenUtau data directory (saved selection or XDG default when omitted)')
    parser.add_argument('--parent-pid', type=int, help='Close and stop owned bridge when the calling OpenUtau exits')
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lock = open(str(config_path) + '.gui.lock', 'a')
    root = tk.Tk()
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        root.withdraw()
        try:
            owner = int(Path(str(config_path) + '.gui.lock').read_text().strip())
            if owner <= 0: raise ValueError('Invalid window owner')
            os.kill(owner, signal.SIGUSR1)
        except (ValueError, OSError):
            messagebox.showinfo('桥接设置', '该配置的设置窗口已打开，请使用已有窗口', parent=root)
        root.destroy(); sys.exit(0)
    try:
        app = SettingsWindow(root,Path(args.config).expanduser().resolve(),Path(args.voices).expanduser().resolve(),args.data_dir, args.parent_pid)
        def show_window(signum, frame):
            root.after(0, lambda: (root.deiconify(), root.lift()))
        signal.signal(signal.SIGUSR1, show_window)
        lock.seek(0);lock.truncate();lock.write(str(os.getpid()));lock.flush()
        if args.parent_pid and config_path.is_file(): root.after(0, app.start)
        root.mainloop()
    except Exception as error:
        messagebox.showerror('桥接设置',str(error),parent=root)
        root.destroy(); sys.exit(1)
