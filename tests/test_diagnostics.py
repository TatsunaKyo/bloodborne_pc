"""Exercise actual subprocess output and retained opt-in sessions on normal/crash exit."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source=Path(__file__).resolve().parents[1]/'launcher/bbport_launcher_win.py'
spec=importlib.util.spec_from_file_location('diagnostics_launcher',source)
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
with tempfile.TemporaryDirectory(prefix='bbport-diagnostics-') as temp:
    launcher.DATA_DIR=Path(temp)
    settings=dict(launcher.APP_DEFAULTS)
    session=launcher.DiagnosticSession(settings)
    assert session.directory is None and not (Path(temp)/'user/diagnostics').exists()
    assert 'BB_DIAGNOSTICS_DIR' not in session.environment({})
    settings.update(developer_profile=True,online_password='DO NOT RECORD THIS',extra_env='SECRET=PRIVATE')
    folders=[]
    for code in (0,3):
        session=launcher.DiagnosticSession(settings)
        env=session.environment({})
        assert env['BB_FRAME_STATS']==env['BB_GPU_PROFILE']=='1'
        assert Path(env['BB_DIAGNOSTICS_DIR']).is_dir()
        child=subprocess.Popen([sys.executable,'-c',f'print("frame data",flush=True);print("Fault test" if {code} else "normal exit",flush=True);raise SystemExit({code})'],stdout=subprocess.PIPE)
        observed=[]
        assert launcher.read_game_output(child,settings,session,observed.append)==code
        metadata=json.loads((session.directory/'session.json').read_text())
        assert metadata['status']=='exited' and metadata['exit_code']==code
        assert metadata['duration_seconds']>=0
        log=(session.directory/'session.log').read_text()
        assert 'frame data' in log and f'Process exited with code {code}' in log
        assert 'DO NOT RECORD THIS' not in json.dumps(metadata) and 'SECRET' not in json.dumps(metadata)
        folders.append(session.directory)
    assert folders[0]!=folders[1] and all((p/'session.log').exists() for p in folders)
    last=(Path(temp)/'user/last_run.log').read_text()
    assert 'Process exited with code 3' in last
    assert f'Bloodborne launcher {launcher.VERSION}' in last
    assert 'Launch settings: ' in last and 'Requested graphics: ' in last
    assert 'DO NOT RECORD THIS' not in last and 'SECRET' not in last
    diagnostic=launcher.DiagnosticSession({**settings,'_nvidia_diagnostic':'inputs'})
    env=diagnostic.environment({'BB_GPU_PROFILE':'1'})
    assert env['BB_HITCH_TRACE']=='1' and 'BB_GPU_PROFILE' not in env
    assert diagnostic.metadata['cpu_hitch_trace']['normal_renderer_preserved']
    assert diagnostic.metadata['renderer_environment']['BB_HITCH_TRACE']=='1'
    assert 'BB_GPU_PROFILE' not in diagnostic.metadata['renderer_environment']
    diagnostic.log.close()
print('PASS: diagnostics disabled by default; separate retained runs, real normal/crash subprocess output, timings/settings/exit code, credential omission and last-run compatibility.')
