# SPDX-License-Identifier: GPL-2.0-or-later
"""Pinned runtime extraction rejects changed data before replacing a DLL."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packaging/windows'))
import fetch_fg401_dx12 as fg

class RuntimeTests(unittest.TestCase):
    def fixture(self,target,corrupt=False):
        payloads={name:('fixture:'+name).encode() for name in fg.FILES}
        records={name:(len(data),hashlib.sha256(data).hexdigest()) for name,data in payloads.items()}
        archive=target/fg.sdk.ARCHIVE_NAME
        with zipfile.ZipFile(archive,'w') as z:
            for name,data in payloads.items():
                z.writestr(fg.MEMBER+name,b'x'*len(data) if corrupt else data)
        return payloads,records,archive

    def extraction(self,target,records,archive):
        return patch.multiple(fg.sdk,ARCHIVE_SIZE=archive.stat().st_size,
                              ARCHIVE_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_verified_extraction_and_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);payloads,records,archive=self.fixture(target)
            with patch.object(fg,'FILES',records),self.extraction(target,records,archive):
                fg.prepare(target)
                self.assertTrue(fg.verified(target))
                for name,data in payloads.items(): self.assertEqual((target/name).read_bytes(),data)
                with patch.object(fg.zipfile,'ZipFile',side_effect=AssertionError('cache reopened')):
                    fg.prepare(target)

    def test_changed_dll_keeps_installed_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);_,records,archive=self.fixture(target,corrupt=True)
            name=next(iter(records));(target/name).write_bytes(b'previous DLL')
            with patch.object(fg,'FILES',records),self.extraction(target,records,archive):
                with self.assertRaises(ValueError): fg.prepare(target)
                self.assertEqual((target/name).read_bytes(),b'previous DLL')

    def test_changed_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);_,records,archive=self.fixture(target)
            download=io.BytesIO(archive.read_bytes())
            with patch.object(fg,'FILES',records),patch.object(fg.sdk,'ARCHIVE_SHA256','0'*64),                 patch.object(fg.sdk.urllib.request,'urlopen',return_value=download):
                with self.assertRaises(ValueError): fg.prepare(target)
                self.assertFalse(any((target/name).exists() for name in records))

    def test_missing_archive_is_fetched_again(self):
        # The FSR 4.1.1 DLL can be cached while the archive is gone: download it again.
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);_,records,archive=self.fixture(target)
            cached=b'verified cached upscaler DLL'
            dll=target/fg.sdk.DLL_NAME
            dll.write_bytes(cached)
            with self.extraction(target,records,archive):
                download=io.BytesIO(archive.read_bytes());archive.unlink()
                with patch.object(fg,'FILES',records), \
                     patch.multiple(fg.sdk,DLL_SIZE=len(cached),DLL_SHA256=hashlib.sha256(cached).hexdigest()), \
                     patch.object(fg.sdk.urllib.request,'urlopen',return_value=download) as urlopen:
                    self.assertTrue(fg.sdk.verified(dll,fg.sdk.DLL_SIZE,fg.sdk.DLL_SHA256))
                    self.assertFalse(archive.exists())
                    fg.prepare(target)
                    self.assertTrue(fg.verified(target))
                    self.assertEqual(dll.read_bytes(),cached)
                    self.assertTrue(fg.sdk.verified(archive,fg.sdk.ARCHIVE_SIZE,fg.sdk.ARCHIVE_SHA256))
                urlopen.assert_called_once()

if __name__=='__main__': unittest.main()
