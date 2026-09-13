"""Tk layout/stop regression; requires a display, no Wine or engine. Uses a temporary port."""
from unittest.mock import patch
import json,socket,subprocess,sys,tempfile,threading,time,os,signal
from pathlib import Path
import tkinter as tk
import zmq
r=Path(__file__).resolve().parents[1];sys.path.insert(0,str(r/'enunu'))
from configure import SettingsWindow
import configure
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder);config=p/'config.json';config.write_text((r/'bridge/config.example.json').read_text())
 root=tk.Tk();app=SettingsWindow(root,config,p/'voices.json',p/'OpenUtau');root.update();root.lift();root.after(200,lambda:None)
 for _ in range(20):root.update();time.sleep(.02)
 button=app.stop_button
 x=button.winfo_rootx()+button.winfo_width()//2;y=button.winfo_rooty()+button.winfo_height()//2
 assert button.winfo_ismapped()
 assert button.master.master.grid_slaves(row=11)==[button.master], 'Service row overlaps another widget'
 assert button.master.grid_info()['row']==11
 root.withdraw()
 # Restoring a hidden window uses a marker file on both platforms, not Unix signals.
 marker=Path(str(config)+'.gui.show');marker.touch();app.poll();root.update()
 assert root.state()!='withdrawn' and not marker.exists()
 root.withdraw()
 # Simulate Windows layout without starting any engine or changing real settings.
 with patch.object(configure,'IS_WINDOWS',True):
  win=tk.Toplevel(root);native=SettingsWindow(win,config,p/'winvoices.json',p/'OpenUtau');root.update()
  assert 'wine' not in native.fields and 'wine_prefix' not in native.fields
  assert native.stop_button.master.grid_info()['row']==11
  native.closing=True;native.poll()
 with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
 ctx=zmq.Context()
 def launch():
  process=subprocess.Popen([sys.executable,str(r/'enunu/server.py'),'--config',str(config),'--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
  app.process=process;app.set_controls()
  def read():
   try:
    for line in process.stdout:app.events.put(('log',line))
   finally:process.stdout.close()
  threading.Thread(target=read,daemon=True).start()
  c=ctx.socket(zmq.REQ);c.setsockopt(zmq.LINGER,0);c.setsockopt(zmq.RCVTIMEO,3000);c.connect(f'tcp://127.0.0.1:{port}')
  try:c.send_json(['ver_check']);assert c.recv_json()['error'] is None
  finally:c.close()
  deadline=time.monotonic()+3
  state=p/'config.json.service.local.json'
  while not state.exists() or not json.loads(state.read_text())['Ready']:
   root.update();assert time.monotonic()<deadline;time.sleep(.02)
  assert json.loads(state.read_text())['Pid']==process.pid
 def stopped():
  deadline=time.monotonic()+5
  while app.process is not None:
   root.update();assert time.monotonic()<deadline;time.sleep(.02)
  assert app.status.get()=='桥接已停止'
  assert not json.loads((p/'config.json.service.local.json').read_text())['Ready']
 try:
  for _ in range(2):
   launch();assert str(button['state'])=='normal';button.invoke();stopped()
  print('PASS: stop button is visible and not covered; real service button stop and restart work')
  # A detached child retains the pipe after its parent exits; Tk must not close
  # the pipe while the reader holds its lock.
  childfile=p/'child.pid'
  script="import subprocess,time,pathlib; c=subprocess.Popen(['sleep','15'],start_new_session=True);pathlib.Path("+repr(str(childfile))+").write_text(str(c.pid));time.sleep(15)"
  process=subprocess.Popen([sys.executable,'-c',script],stdout=subprocess.PIPE,text=True,start_new_session=True)
  deadline=time.monotonic()+5
  while not childfile.exists():assert time.monotonic()<deadline;time.sleep(.01)
  child=int(childfile.read_text());app.process=process;app.set_controls()
  def reader():
   try:process.stdout.read()
   finally:process.stdout.close()
  threading.Thread(target=reader,daemon=True).start()
  try:
   button.invoke();start=time.monotonic();stopped();assert time.monotonic()-start<1
   print('PASS: inherited log pipe does not freeze the settings window on Stop')
  finally:os.kill(child,signal.SIGTERM)
 finally:
  app.stop()
  if app.process:app.process.wait(timeout=5)
  root.destroy();ctx.term()
