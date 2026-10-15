# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('dlssg_mod',Path(__file__).resolve().parents[1]/'scripts/dlssg_mod.py')
m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Mod(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=self.root/'settings.ini';self.probe=self.root/'bin/bb-probe.exe'
        self.calls=[]
    def tearDown(self): self.tmp.cleanup()
    def settings(self,text): self.config.with_suffix('.menu.ini').write_text(text)
    def probe_run(self,args,**kw):
        self.calls.append(args)
        return type('Result',(),{'returncode':0,'stdout':self.answer})()
    def download(self,path): self.calls.append(path)
    def launch(self):
        return m.configure_launch(self.config,self.probe,{},windows=True,run=self.probe_run,download=self.download)
    def test_default_zero_activity(self):
        self.answer='1';self.assertIn('off',self.launch());self.assertEqual(self.calls,[])
    def test_fsr_zero_activity(self):
        self.settings('nvidia_fg_mod=1\nframe_generation=fsr');self.answer='1'
        self.assertIn('off',self.launch());self.assertEqual(self.calls,[])
    def test_unsupported_and_malformed_no_download(self):
        self.settings('nvidia_fg_mod=1\nframe_generation=nvidia')
        for value in ('0','', '1\n0','GeForce RTX 4090'):
            self.calls=[];self.answer=value;self.assertIn('nothing downloaded',self.launch());self.assertEqual(len(self.calls),1)
    def test_eligible_download_once(self):
        self.settings('nvidia_fg_mod=1\nframe_generation=nvidia');self.answer='1'
        self.assertIn('provider ready',self.launch());self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[1],self.probe.parent/'mods/dlssg')
    def test_custom_provider_precedence(self):
        self.settings('nvidia_fg_mod=1\nframe_generation=nvidia');self.answer='1'
        path=self.probe.parent/'mods/dlssg/dlssg_sm86.dll';path.parent.mkdir(parents=True);path.write_bytes(b'user file')
        self.assertIn('explicitly supplied',self.launch());self.assertEqual(len(self.calls),1)
    def test_download_failure_keeps_original(self):
        self.settings('nvidia_fg_mod=1\nframe_generation=nvidia');self.answer='1'
        def fail(path): raise OSError('offline')
        self.assertIn('Original NVIDIA path retained',m.configure_launch(self.config,self.probe,{},windows=True,run=self.probe_run,download=fail))
    def test_tampered_download_never_installed(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*a): self.close()
        with self.assertRaises(ValueError):
            m.download_provider(self.root/'provider',lambda *a,**kw:Response(b'wrong release'))
        self.assertFalse((self.root/'provider/rtx-encore.asi').exists())


if __name__=='__main__': unittest.main()
