"""Check one-run geometry comparisons without changing the user's saved preferences."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

source=Path(__file__).resolve().parents[1]/'launcher/bbport_launcher_win.py'
if len(sys.argv)>1:
    import marshal
    import types
    from PyInstaller.archive.readers import CArchiveReader
    launcher=types.ModuleType('geometry_launcher');launcher.__file__=str(source)
    exec(marshal.loads(CArchiveReader(sys.argv[1]).extract('bbport_launcher_win')),launcher.__dict__)
else:
    spec=importlib.util.spec_from_file_location('geometry_launcher',source)
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
with tempfile.TemporaryDirectory(prefix='bb-geometry-diagnostics-') as directory:
    launcher.DATA_DIR=Path(directory)
    settings=dict(launcher.APP_DEFAULTS,draw_pipe='1',developer_profile=False,
                  extra_env='BB_PREP_WORKERS=8 BB_VK_RECORD_THREAD=1 BB_COPY_THREADS=4 SECRET=PRIVATE')
    original=dict(settings)
    assert launcher.geometry_diagnostic_settings(settings,[]) is settings
    assert launcher.geometry_diagnostic_settings(settings,['--geometry-diagnostic=unknown']) is settings
    folders=[]
    for mode in ('normal','serial'):
        selected=launcher.geometry_diagnostic_settings(settings,['--play','--geometry-diagnostic='+mode])
        assert selected['developer_profile'] and selected['_geometry_diagnostic']==mode
        session=launcher.DiagnosticSession(selected)
        env=session.environment(launcher.game_environment(selected))
        keys=('BB_DRAW_PIPE','BB_PREP_WORKERS','BB_VK_RECORD_THREAD','BB_COPY_THREADS')
        expected=('1','8','1','4') if mode=='normal' else ('0','0','0','0')
        assert tuple(env[k] for k in keys)==expected
        session.finish(0)
        metadata=json.loads((session.directory/'session.json').read_text())
        assert metadata['geometry_diagnostic']==mode
        assert tuple(metadata['renderer_environment'][k] for k in keys)==expected
        assert 'SECRET' not in json.dumps(metadata) and 'PRIVATE' not in json.dumps(metadata)
        assert 'Geometry diagnostic: '+mode in (session.directory/'session.log').read_text()
        folders.append(session.directory)
    assert folders[0]!=folders[1]
    assert settings==original
    assert not (Path(directory)/'launcher.json').exists()
    session=launcher.DiagnosticSession(settings)
    assert session.directory is None
    assert tuple(launcher.game_environment(settings)[k] for k in keys)==('1','8','1','4')
print('PASS: normal/serial geometry runs keep independent diagnostics, record actual thread settings, override conflicts only for the reference run, preserve preferences and keep normal profiling off.')
