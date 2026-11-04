"""The fork updater stays on stable TatsunaKyo releases."""
from paths import ROOT
import io
import json
import sys
import unittest
from unittest import mock
sys.path.insert(0, str(ROOT / 'launcher'))
import bbport_launcher_win as L


def release(version, **flags):
    return {'tag_name': 'windows-v' + version,
            'assets': [{'name': L.update_package_name(version), 'browser_download_url': 'https://example.invalid/game.zip'}],
            **flags}


class ReleaseChannelTests(unittest.TestCase):
    def offer(self, data):
        with mock.patch.object(L.bbport_tls, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as request:
            found = L.update_to_offer()
        self.assertEqual(request.call_args.args[0].full_url, L.RELEASES_API)
        self.assertEqual(request.call_count, 1)
        return found

    def test_own_newer_stable_release(self):
        self.assertEqual(self.offer(release('9.9.9-tatsunakyo.1'))[:2],
                         ('9.9.9-tatsunakyo.1', 'https://example.invalid/game.zip'))

    def test_same_or_older_release_is_not_offered(self):
        self.assertIsNone(self.offer(release(L.VERSION)))
        self.assertIsNone(self.offer(release('1.6-tatsunakyo.55')))

    def test_drafts_and_prereleases_are_refused(self):
        for flag in ('draft', 'prerelease'):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.offer(release('9.9.9-tatsunakyo.1', **{flag: True}))

    def test_other_projects_are_refused(self):
        for tag in ('windows-v9.9.9', 'v9.9.9-beta.1'):
            data = release('9.9.9-tatsunakyo.1'); data['tag_name'] = tag
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.offer(data)

    def test_network_error_reaches_the_manual_update_handler(self):
        with mock.patch.object(L.bbport_tls, 'urlopen', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                L.update_to_offer()


if __name__ == '__main__':
    unittest.main()
