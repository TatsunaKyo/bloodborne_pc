# SPDX-License-Identifier: GPL-2.0-or-later
"""Windows fsr4vk packaging: require verified source and stage only verified files."""
from paths import ROOT
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('package_fsr4vk', ROOT/'packaging/windows/prepare_fsr4vk.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)
fetch = package.provider


class Fsr4VkPackageTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cache = Path(temporary.name)/'cache'
        self.cache.mkdir()
        self.source = b'pinned corresponding source archive'
        members = {'amd_fidelityfx_upscaler_vk.dll': b'MZ verified provider',
                   'LICENSES/GPL-3.0.txt': b'gpl',
                   'LICENSES/AMD-FidelityFX-SDK-MIT.md': b'mit',
                   'LICENSES/Zstandard-BSD.txt': b'bsd', 'PATCH.md': b'AMD patch'}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        self.binary = buffer.getvalue()
        overrides = [(package, 'SOURCE_SIZE', len(self.source)),
                     (package, 'SOURCE_SHA256', hashlib.sha256(self.source).hexdigest()),
                     (fetch, 'ZIP_SIZE', len(self.binary)),
                     (fetch, 'ZIP_SHA256', hashlib.sha256(self.binary).hexdigest()),
                     (fetch, 'FILES', tuple((name, name, len(data), hashlib.sha256(data).hexdigest())
                                           for name, data in members.items() if name != 'PATCH.md'))]
        for module, name, value in overrides:
            override = patch.object(module, name, value)
            override.start()
            self.addCleanup(override.stop)
        part = self.cache/'provider/.download'/(fetch.ZIP_NAME+'.part')
        part.parent.mkdir(parents=True)
        part.write_bytes(self.binary)

    def provide_source(self):
        path = self.cache/package.SOURCE_NAME
        path.write_bytes(self.source)
        return path

    def test_cold_cache_downloads_pinned_source_and_stages_only_provider_files(self):
        with patch.object(package.urllib.request, 'urlopen', return_value=io.BytesIO(self.source)) as download:
            target = package.prepare(self.cache)
        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args[0].full_url, fetch.SOURCE_ZIP_URL)
        self.assertTrue(fetch.files_ok(target))
        (target/'unrelated-private.txt').write_bytes(b'keep out of package')
        (target/'.download').mkdir()
        (target/'.download/incomplete.part').write_bytes(b'incomplete')
        destination = self.cache.parent/'stage/fsr4vk'
        package.stage_provider(target, destination)
        self.assertTrue(fetch.files_ok(destination))
        self.assertFalse((destination/'unrelated-private.txt').exists())
        self.assertFalse((destination/'.download').exists())
        self.assertFalse((destination/package.SOURCE_NAME).exists())
        self.assertEqual((destination/'PATCH.md').read_bytes(), b'AMD patch')
        self.assertIn(package.SOURCE_NAME, (destination/'SOURCE.txt').read_text())

    def test_verified_cache_is_reused_without_network(self):
        self.provide_source()
        with patch.object(package.urllib.request, 'urlopen', side_effect=AssertionError('unexpected network')):
            target = package.prepare(self.cache)
            (target/'SOURCE.txt').write_text('outdated notice')
            self.assertEqual(package.prepare(self.cache), target)
        self.assertIn(package.SOURCE_NAME, (target/'SOURCE.txt').read_text())

    def test_wrong_source_is_rejected_before_provider_preparation(self):
        old = self.provide_source()
        old.write_bytes(b'previous invalid source')
        with patch.object(package.urllib.request, 'urlopen', return_value=io.BytesIO(b'untrusted data')), \
             patch.object(fetch, 'fetch') as prepare_provider:
            with self.assertRaisesRegex(ValueError, 'source archive size or SHA-256'):
                package.prepare(self.cache)
        self.assertEqual(old.read_bytes(), b'previous invalid source')
        self.assertFalse(list(self.cache.glob('*.part')))
        prepare_provider.assert_not_called()

    def test_equal_size_source_with_wrong_hash_is_rejected(self):
        with patch.object(package.urllib.request, 'urlopen', return_value=io.BytesIO(b'X'*len(self.source))):
            with self.assertRaisesRegex(ValueError, 'source archive size or SHA-256'):
                package.prepare_source(self.cache)
        self.assertFalse((self.cache/package.SOURCE_NAME).exists())
        self.assertFalse(list(self.cache.glob('*.part')))

    def test_interrupted_source_download_cleans_up(self):
        response = io.BytesIO(self.source)
        with patch.object(package.urllib.request, 'urlopen', return_value=response), \
             patch.object(package.shutil, 'copyfileobj', side_effect=OSError('interrupted')):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                package.prepare_source(self.cache)
        self.assertFalse((self.cache/package.SOURCE_NAME).exists())
        self.assertFalse(list(self.cache.glob('*.part')))

    def test_source_failure_keeps_previously_verified_provider(self):
        source = self.provide_source()
        target = package.prepare(self.cache)
        source.unlink()
        with patch.object(package.urllib.request, 'urlopen', side_effect=OSError('offline')):
            with self.assertRaisesRegex(OSError, 'offline'):
                package.prepare(self.cache)
        self.assertTrue(fetch.files_ok(target))

    def test_cached_changed_provider_is_repaired(self):
        self.provide_source()
        target = package.prepare(self.cache)
        (target/fetch.FILES[0][1]).write_bytes(b'damaged')
        with patch.object(fetch, '_download', side_effect=lambda part, progress: part.write_bytes(self.binary)):
            package.prepare(self.cache)
        self.assertTrue(fetch.files_ok(target))

    def test_invalid_staged_provider_stops_packaging(self):
        self.provide_source()
        target = package.prepare(self.cache)
        (target/fetch.FILES[0][1]).write_bytes(b'damaged')
        with self.assertRaisesRegex(ValueError, 'staged fsr4vk'):
            package.stage_provider(target, self.cache.parent/'stage')


if __name__ == '__main__':
    unittest.main()
