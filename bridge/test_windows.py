"""Simulate native Windows launch without proprietary APIs; Linux tests remain separate."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import host,settings,platform_support as platform

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder); api=root/'API with spaces'; (api/'v6api').mkdir(parents=True); (api/'v6api/__init__.py').touch()
    editor=root/'Editor';editor.mkdir()
    for name in ('VDM.dll','DSE.dll','VSM.dll'):(editor/name).touch()
    config=dict(api_dir=str(api),windows_python=sys.executable,vocaloid_dir=str(editor),common_dir=str(root),timeout_seconds=2)
    path=root/'config.json';path.write_text(json.dumps(config))
    reply=subprocess.CompletedProcess([],0,'{"ok":true,"voices":[]}', '')
    with patch.object(settings,'IS_WINDOWS',True),patch.object(host,'IS_WINDOWS',True):
        value=settings.validate(config)
        assert value['wine']==value['wine_prefix']==''
        assert value['vocaloid_dir']==str(editor)
        with patch.object(host.subprocess,'run',return_value=reply) as run:
            host.invoke(path,'list');argv=run.call_args.args[0]
            assert argv[:3]==[str(Path(sys.executable).resolve()),str(Path(host.__file__).with_name('worker.py')),'list']
            assert argv[argv.index('--api-dir')+1]==str(api)
            assert not any(x.startswith('Z:') for x in argv)
            assert run.call_args.kwargs['env']['PYTHONIOENCODING']=='utf-8'
        worker=Mock();worker.render.return_value={'ok':True}
        with patch.object(host,'Worker',return_value=worker) as create:
            host.enable_persistent()
            try:
                host.invoke(path,'render',root/'request',root/'out')
                host.invoke(path,'render',root/'request',root/'out')
                assert create.call_count==1
                argv=create.call_args.args[0]
                assert argv[:3]==[str(Path(sys.executable).resolve()),str(Path(host.__file__).with_name('worker.py')),'serve']
                assert '--request' not in argv
            finally:host.close_worker();host._persistent=False
            worker.close.assert_called_once()
    process=Mock(pid=12345);process.poll.return_value=None
    with patch.object(platform,'IS_WINDOWS',True),patch.object(platform.subprocess,'Popen') as kill:
        platform.stop_tree(process)
        assert kill.call_args.args[0]==['taskkill','/PID','12345','/T','/F']
    assert platform.process_alive(os.getpid()) and not platform.process_alive(0)
    # Check both platforms' default data selection and the native lock/reopen mechanism.
    with patch.object(platform,'IS_WINDOWS',True):assert platform.data_directory().name=='OpenUtau'
    first=(root/'gui.lock').open('a+b'); second=(root/'gui.lock').open('a+b')
    try:
        platform.lock_window(first)
        try:platform.lock_window(second)
        except BlockingIOError:pass
        else:raise AssertionError('Duplicate settings lock accepted')
    finally:first.close();second.close()
print('PASS: simulated Windows validation, spaced native paths, no Wine/Z: mapping, persistent reuse, owned process-tree stop; native lock')
