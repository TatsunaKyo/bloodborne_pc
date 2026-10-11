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
    for mode in ('normal','serial','capture'):
        selected=launcher.geometry_diagnostic_settings(settings,['--play','--geometry-diagnostic='+mode])
        assert selected['developer_profile'] and selected['_geometry_diagnostic']==mode
        session=launcher.DiagnosticSession(selected)
        env=session.environment(launcher.game_environment(selected))
        keys=('BB_DRAW_PIPE','BB_PREP_WORKERS','BB_VK_RECORD_THREAD','BB_COPY_THREADS')
        expected=('1','8','1','4') if mode=='normal' else ('0','0','0','0')
        assert tuple(env[k] for k in keys)==expected
        if mode == 'capture':
            assert env['BB_GEOMETRY_CAPTURE'] == '1' and env['BB_DUMP_FRAMES'] == '8'
            assert env['BB_DUMP_POLL_FRAMES'] == '1'
            assert Path(env['BB_DUMP_DIR']).is_dir()
            assert Path(env['BB_CAPTURE_DIR']).is_dir()
            assert Path(env['BB_DUMP_TRIGGER']).parent == session.directory.resolve()
            # Package renderer-produced data, including arbitrary binary bytes.
            for frame in range(8):
                (Path(env['BB_DUMP_DIR'])/f'f{frame:03d}_input_1x1_rgba.raw').write_bytes(bytes((frame,0,255,128)))
                (Path(env['BB_DUMP_DIR'])/f'f{frame:03d}_output_1x1_rgba16f.raw').write_bytes(b'\x00\x00\x00\x3c'*2)
            (Path(env['BB_CAPTURE_DIR'])/'frame_1.txt').write_text('presented buffer; bound resources')
            (session.directory/'unrelated-secret.txt').write_text('DO NOT INCLUDE')
        session.finish(0)
        metadata=json.loads((session.directory/'session.json').read_text())
        assert metadata['geometry_diagnostic']==mode
        assert tuple(metadata['renderer_environment'][k] for k in keys)==expected
        assert 'SECRET' not in json.dumps(metadata) and 'PRIVATE' not in json.dumps(metadata)
        assert 'Geometry diagnostic: '+mode in (session.directory/'session.log').read_text()
        if mode == 'capture':
            import zipfile
            with zipfile.ZipFile(session.directory/'Flashing-assets-diagnostic.zip') as archive:
                assert archive.testzip() is None
                assert len(archive.namelist()) == 19
                assert archive.read('frames/f003_input_1x1_rgba.raw') == bytes((3,0,255,128))
                assert 'unrelated-secret.txt' not in archive.namelist()
                assert json.loads(archive.read('session.json'))['frame_capture']['position']=='before_frame_generation'
            assert metadata['frame_capture']['raw_files']==16
            assert metadata['frame_capture']['paired_frames']==8
            assert metadata['frame_capture']['status']=='captured'
        folders.append(session.directory)
    assert folders[0]!=folders[1]
    assert settings==original
    assert not (Path(directory)/'launcher.json').exists()
    # An unarmed run reports missing captures; it never invents a successful bundle.
    empty=launcher.DiagnosticSession(launcher.geometry_diagnostic_settings(settings,['--geometry-diagnostic=capture']))
    empty.environment(launcher.game_environment(settings))
    empty.finish(0)
    assert json.loads((empty.directory/'session.json').read_text())['frame_capture']['status']=='no_frames'
    assert not (empty.directory/'Flashing-assets-diagnostic.zip').exists()
    partial=launcher.DiagnosticSession(launcher.geometry_diagnostic_settings(settings,['--geometry-diagnostic=capture']))
    partial_env=partial.environment(launcher.game_environment(settings))
    (Path(partial_env['BB_DUMP_DIR'])/'f000_input_1x1_rgba.raw').write_bytes(b'\x00'*4)
    partial.finish(1)
    assert json.loads((partial.directory/'session.json').read_text())['frame_capture']['status']=='incomplete'
    # An archive write failure leaves the native capture intact and reports failure.
    from unittest.mock import patch
    failed=launcher.DiagnosticSession(launcher.geometry_diagnostic_settings(settings,['--geometry-diagnostic=capture']))
    failed_env=failed.environment(launcher.game_environment(settings))
    raw=Path(failed_env['BB_DUMP_DIR'])/'f000_input_1x1_rgba.raw'; raw.write_bytes(b'\x00'*4)
    with patch.object(launcher.zipfile,'ZipFile',side_effect=OSError('fixture disk write failure')):
        failed.finish(0)
    assert raw.read_bytes()==b'\x00'*4
    assert json.loads((failed.directory/'session.json').read_text())['frame_capture']['status']=='archive_failed'
    assert not (failed.directory/'Flashing-assets-diagnostic.zip').exists()
    session=launcher.DiagnosticSession(settings)
    assert session.directory is None
    assert tuple(launcher.game_environment(settings)[k] for k in keys)==('1','8','1','4')
print('PASS: normal/serial/capture runs preserve preferences; effective renderer flags are logged; F8 captures archive byte-exact inputs/outputs and pass records; unrelated files are excluded; unarmed runs report no frames; ordinary profiling remains opt-in.')
