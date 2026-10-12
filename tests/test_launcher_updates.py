"""Keep fork updates on the revision channel, including the compiled Windows launcher."""
import importlib.util
import ast
import io
import json
import queue
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

source = Path(__file__).resolve().parents[1] / 'launcher/bbport_launcher_win.py'
if len(sys.argv) > 1:
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    executable = sys.argv.pop(1)
    launcher = types.ModuleType('bbport_launcher_update_test')
    launcher.__file__ = str(source)
    exec(marshal.loads(CArchiveReader(executable).extract('bbport_launcher_win')), launcher.__dict__)
else:
    spec = importlib.util.spec_from_file_location('bbport_launcher_update_test', source)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)


source_version = next(n.value.value for n in ast.parse(source.read_text()).body
                      if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in n.targets))
future_revision = int(source_version.rsplit('.', 1)[1]) + 1
future_version = source_version.rsplit('.', 1)[0] + '.' + str(future_revision)

class ForkUpdates(unittest.TestCase):
    def release(self, tag=None, assets=None):
        tag = tag or 'windows-v' + future_version
        return {'tag_name': tag, 'html_url': 'https://github.com/TatsunaKyo/bloodborne_pc/releases/tag/' + tag,
                'assets': assets if assets is not None else [
                    {'name': 'source.zip', 'browser_download_url': 'https://example.invalid/source.zip'},
                    {'name': f'Bloodborne-Windows-v1.6-TatsunaKyo-Revision-{future_revision}.zip',
                     'browser_download_url': 'https://example.invalid/windows.zip'}]}

    def latest(self, release):
        with patch.object(launcher.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(release).encode())) as request:
            result = launcher.latest_release()
        self.assertEqual(request.call_args.args[0].full_url,
                         'https://api.github.com/repos/TatsunaKyo/bloodborne_pc/releases/latest')
        return result

    def check(self, release, manual=False):
        app = launcher.Launcher.__new__(launcher.Launcher)
        app.ui_calls = queue.Queue()
        calls = []
        app.offer_update = lambda *args: calls.append(('update', args))
        app.messagebox = types.SimpleNamespace(
            showinfo=lambda *args: calls.append(('info', args)),
            showerror=lambda *args: calls.append(('error', args)))
        with patch.object(launcher.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(release).encode())):
            app.check_update(manual)
        while not app.ui_calls.empty():
            app.ui_calls.get_nowait()()
        return calls

    def test_channel_and_exact_windows_asset(self):
        self.assertEqual(launcher.VERSION, source_version)
        self.assertEqual(launcher.RELEASES_PAGE, 'https://github.com/TatsunaKyo/bloodborne_pc/releases/latest')
        version, url, page = self.latest(self.release())
        self.assertEqual((version, url), (future_version, 'https://example.invalid/windows.zip'))
        self.assertTrue(page.endswith('/windows-v' + future_version))

    def test_published_stable_preview_tags(self):
        release = json.loads((source.parents[1] / 'tests/fixtures/release21-stable.json').read_text())
        version, url, _page = self.latest(release)
        self.assertEqual(version, '1.6-tatsunakyo.21')
        self.assertTrue(url.endswith('/Bloodborne-Windows-v1.6-TatsunaKyo-Revision-21.zip'))
        for revision in (19, 21, future_revision):
            candidate = self.release(f'windows-v1.6-tatsunakyo.{revision}-preview', assets=[
                {'name':f'Bloodborne-Windows-v1.6-TatsunaKyo-Revision-{revision}.zip',
                 'browser_download_url':'https://example.invalid/windows.zip', 'state':'uploaded'}])
            candidate['prerelease'] = False
            self.assertEqual(self.latest(candidate)[0],f'1.6-tatsunakyo.{revision}')

    def test_actual_prereleases_and_drafts_are_not_offered(self):
        for tag in ('windows-v'+future_version, 'windows-v'+future_version+'-preview'):
            for flag in ('prerelease','draft'):
                release = self.release(tag); release[flag] = True
                with self.subTest(tag=tag,flag=flag), self.assertRaises(ValueError):
                    self.latest(release)
                self.assertEqual(self.check(release), [])

    def test_malformed_or_unready_release(self):
        for release in ({}, [], {'tag_name':None}, {'tag_name':42}, {'tag_name':'windows-v'+future_version,'assets':{}}):
            with self.subTest(release=release), self.assertRaises(ValueError):
                self.latest(release)
        release = self.release(); release['assets'][-1]['state'] = 'new'
        self.assertIsNone(self.latest(release)[1])
        release = self.release(); release['assets'].append(dict(release['assets'][-1]))
        self.assertIsNone(self.latest(release)[1])
        release = self.release(); release['assets'][-1]['browser_download_url'] = 'file:///tmp/package.zip'
        with self.assertRaises(ValueError): self.latest(release)

    def test_source_zip_is_not_installed(self):
        self.assertIsNone(self.latest(self.release(assets=[
            {'name': 'source.zip', 'browser_download_url': 'https://example.invalid/source.zip'}]))[1])

    def test_other_release_channels_are_rejected(self):
        for tag in ('windows-v1.7', 'v1.6', 'linux-v1.6-tatsunakyo.2',
                    'windows-v1.6-tatsunakyo.2-beta', 'windows-v1.6-tatsunakyo.x'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.latest(self.release(tag))
            self.assertEqual(self.check(self.release(tag)), [])
        self.assertEqual(self.check(self.release('windows-v1.7'), manual=True)[0][0], 'error')

    def test_revision_comparison_and_offer(self):
        self.assertEqual(self.check(self.release('windows-v' + source_version)), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.15')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.13')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.12')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.11')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.10')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.6')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.5')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.2')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.1')), [])
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.0')), [])
        self.assertEqual(self.check(self.release())[0][0], 'update')
        self.assertEqual(self.check(self.release('windows-v1.7-tatsunakyo.1'))[0][0], 'update')
        self.assertGreater(launcher.version_tuple('1.6-tatsunakyo.11'),
                           launcher.version_tuple('1.6-tatsunakyo.2'))
        self.assertEqual(self.check(self.release('windows-v1.6-tatsunakyo.1'), manual=True)[0][0], 'info')

    def test_no_published_release_is_quiet_on_startup(self):
        app = launcher.Launcher.__new__(launcher.Launcher)
        app.ui_calls = queue.Queue()
        error = HTTPError(launcher.RELEASES_API, 404, 'Not Found', {}, None)
        try:
            with patch.object(launcher.urllib.request, 'urlopen', side_effect=error):
                app.check_update()
        finally:
            error.close()
        self.assertTrue(app.ui_calls.empty())


if __name__ == '__main__':
    unittest.main()
