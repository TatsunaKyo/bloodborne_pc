# SPDX-License-Identifier: GPL-2.0-or-later
"""Replay actual packaged launch/patch decisions with a synthetic ELF and a recording probe.

The ELF contains no game code. Only preparation/linking and the game process are stand-ins;
run.py, patch fingerprinting/compilation, save preparation and launcher policy are production.
This validates startup decisions, not game performance or hardware FG.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def fixture(xml):
    compiler=load(ROOT/'scripts/patches.py','fixture_compiler')
    names=[*compiler.FINGERPRINT_PATCHES,'Disable AA']
    ranges=compiler.patch_sites(xml,'01.09',names)
    header=bytearray(64+56*len(ranges));header[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<Q',header,0x20,64);struct.pack_into('<HH',header,0x36,56,len(ranges))
    body=bytearray()
    for index,(start,end) in enumerate(ranges):
        data=bytes((index*17+j*31+1)%256 for j in range(end-start))
        struct.pack_into('<IIQQQQQQ',header,64+index*56,1,7,len(header)+len(body),start,0,len(data),len(data),1)
        body.extend(data)
    elf=bytes(header+body)
    expected={mode:[[offset,data.hex()] for offset,data in compiler.compile_patches(
        xml,names,'01.09',compiler.eboot_segments(elf))] for mode,names in compiler.FPS_PRESETS.items()}
    first=compiler.patch_sites(xml,'01.09')[0][0]
    index=next(i for i,(start,end) in enumerate(ranges) if start<=first<end)
    file_offset=struct.unpack_from('<Q',elf,64+56*index+8)[0]+first-ranges[index][0]
    return elf,{'fingerprint':compiler.patch_fingerprint(elf,xml),'fps_writes':expected,'corrupt_offset':file_offset}


def child(stage,specification,control=False,compiled=False):
    stage=stage.resolve();spec=json.loads(specification.read_text());reject=spec.get('reject',False)
    sys.path[:0]=[str(stage/'scripts'),str(stage/'tools'),str(stage/'launcher')]
    compiler=load(stage/'scripts/patches.py','patches');sys.modules['patches']=compiler
    # A synthetic fixture cannot have the retail digest. Pin its expected digest
    # from the current source schema, independently of the XML actually shipped.
    compiler.PATCH_FINGERPRINTS['01.09']=spec['fingerprint']
    run=load(stage/'run.py','packaged_run')
    run.no_console=lambda:0 # host adaptation of the Win32 console query, no process creation
    game=stage/'fixture-game';game.mkdir()
    (game/'eboot.bin').write_bytes(b'synthetic fixture, no game code')
    data=stage/'fixture-data';data.mkdir();out=data/'out';out.mkdir()
    probe=stage/'recording-probe.exe';probe.touch()
    env=dict(os.environ)
    for key in list(os.environ):
        if key.startswith('BB_'):os.environ.pop(key)
    os.environ.update(BB_GAME_DIR=str(game),BB_DATA_DIR=str(data),BB_CONFIG=str(data/'bbport.ini'),
        BB_PROBE=str(probe),BB_SKIP_GAME_CHECK='1',BB_SAVE_AUTO_BACKUP='0')
    current={};records=[]
    def script(name,*args,capture=False,optional=False):
        args=list(map(str,args))
        if name=='mods.py':return str(game)
        if name=='prepare.py':(out/'eboot.elf').write_bytes((stage/'fixture.elf').read_bytes());return
        if name in ('link_libc.py','link_modules.py','content_profile.py'):return
        if name=='patches.py':
            if '--fps' in args:current['applied']=args[args.index('--fps')+1]
            old=sys.argv;sys.argv=[str(stage/'scripts/patches.py'),*args]
            try:
                with contextlib.redirect_stdout(io.StringIO()) as output:compiler.main()
                return output.getvalue() if capture else None
            finally:sys.argv=old
        if optional:return None if capture else False
        raise AssertionError('Unexpected preparation boundary: '+name)
    run.run_script=script
    import background
    def record(command,**kwargs):
        raw=(out/'patches.bin').read_bytes();magic,base,count=struct.unpack_from('<8sQQ',raw)
        assert magic==b'BBPATCH2';pos=24;writes={}
        for _ in range(count):
            offset,length=struct.unpack_from('<QQ',raw,pos);pos+=16
            writes.update({offset+i:value for i,value in enumerate(raw[pos:pos+length])});pos+=length
        actual=kwargs['env'];requested=current['requested']
        if control or reject:
            assert current['applied']=='30' and count==0,(current,count)
            assert actual['BB_VBLANK_HZ']=='60'
            if reject:assert actual['BB_FPS']=='30'
        else:
            assert current['applied']==requested,(current,count)
            expected={}
            for offset,hexdata in spec['fps_writes'][requested]:
                expected.update({offset+i:value for i,value in enumerate(bytes.fromhex(hexdata))})
            for offset,value in expected.items():
                assert writes.get(offset)==value,(requested,hex(offset))
            assert actual['BB_FPS']==requested
            assert actual['BB_VBLANK_HZ']=={'uncap':'0','90':'90'}.get(requested,'60'),actual
        assert 'real_fps_limit=60' in (data/'bbport.menu.ini').read_text()
        records.append({'requested':requested,'provider':current['provider'],'applied':current['applied'],
                        'vblank':actual['BB_VBLANK_HZ'],'patch_writes':count})
        return 0
    background.run_game=record
    cases=[('uncap',p) for p in ('off','nvidia','native_fsr','native_dlss','off')]
    if not control and not reject:cases += [('60','off'),('90','native_fsr'),('uncap','off')]
    old_argv=sys.argv;sys.argv=[str(stage/'run.py')]
    for requested,provider in cases:
        current.update(requested=requested,provider=provider);os.environ['BB_FPS']=requested
        (data/'bbport.ini').write_text('upscaler=dlss\npreset=3\noutput_res=1920x1080\nquit_to_desktop=0\n')
        (data/'bbport.menu.ini').write_text(f'frame_generation={provider}\nreal_fps_limit=60\n')
        with contextlib.redirect_stdout(io.StringIO()):assert run.main()==0
    sys.argv=old_argv
    if control:
        module=load(stage/'launcher/bbport_launcher_win.py','old_startup_launcher')
        settings=dict(module.APP_DEFAULTS,frame_cap='30',real_fps_limit='-1',fps_mode='uncap')
        os.environ['BB_FPS_LIMIT']='30'
        assert module.game_environment(settings)['BB_FPS_LIMIT']=='30'
    else:
        if compiled:
            import marshal
            from PyInstaller.archive.readers import CArchiveReader
            module=types.ModuleType('compiled_launcher');module.__file__=str(stage/'_internal/bbport_launcher_win.py')
            original_executable=sys.executable;sys.executable=str(stage/'Bloodborne.exe');sys.frozen=True
            try:exec(marshal.loads(CArchiveReader(sys.executable).extract('bbport_launcher_win')),module.__dict__)
            finally:sys.executable=original_executable;del sys.frozen
        else:module=load(stage/'launcher/bbport_launcher_win.py','startup_launcher')
        settings=dict(module.APP_DEFAULTS,frame_cap='30',fps_mode='75')
        for selected,expected in (('-1',None),('0','0'),('60','60'),('120','120')):
            settings['real_fps_limit']=selected;os.environ['BB_FPS_LIMIT']='30'
            actual=module.game_environment(settings)
            assert actual.get('BB_FPS_LIMIT')==expected,(selected,actual.get('BB_FPS_LIMIT'))
        settings.update(real_fps_limit='-1',extra_env='BB_FPS_LIMIT=90')
        assert module.game_environment(settings)['BB_FPS_LIMIT']=='90' # explicit advanced override
    os.environ.clear();os.environ.update(env)
    print(json.dumps({'control':control,'compiled_launcher':compiled,'cases':records}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path);parser.add_argument('--control',action='store_true')
    parser.add_argument('--compiled',action='store_true');parser.add_argument('--child',type=Path)
    parser.add_argument('--reject',action='store_true',help='Verify incompatible code is still rejected')
    parser.add_argument('--specification',type=Path);args=parser.parse_args()
    if args.child:return child(args.child,args.specification,args.control,args.compiled)
    elf,spec=fixture(ROOT/'patches/Bloodborne.xml')
    if args.reject:
        corrupt=bytearray(elf);corrupt[spec['corrupt_offset']]^=0xff;elf=bytes(corrupt);spec['reject']=True
    with tempfile.TemporaryDirectory(prefix='packaged-startup-') as temporary:
        stage=Path(temporary)
        if args.package:
            with zipfile.ZipFile(args.package) as archive:
                root=next(n.rsplit('/',1)[0]+'/' for n in archive.namelist() if n.endswith('/BUILD-IDENTITY.json'))
                for name in archive.namelist():
                    if not name.startswith(root) or name.endswith('/'):continue
                    relative=name[len(root):]
                    if relative in ('run.py','Bloodborne.exe') or relative.startswith(('scripts/','tools/','patches/','launcher/')):
                        path=stage/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(name))
        else:
            for name in ('scripts','tools','patches','launcher'):
                shutil.copytree(ROOT/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            shutil.copy2(ROOT/'run.py',stage/'run.py')
        (stage/'fixture.elf').write_bytes(elf);(stage/'spec.json').write_text(json.dumps(spec))
        command=[sys.executable,str(Path(__file__).resolve()),'--child',str(stage),'--specification',str(stage/'spec.json')]
        if args.control:command.append('--control')
        if args.compiled:command.append('--compiled')
        subprocess.run(command,check=True,cwd=stage,timeout=120)
    print('PASS: '+('R53 shipped files reproduce the 30-FPS fallback with FG on and off.' if args.control else
        'incompatible executable retains the patch guard and passes the resolved 30-FPS mode to the renderer.' if args.reject else
        'packaged timing patches, FG on/off/restart, Auto/explicit real caps and inherited vblank decisions.'))


if __name__=='__main__':main()
