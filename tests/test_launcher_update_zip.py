"""The update downloads the game's package, not whichever .zip a release lists first
(launcher/bbport_launcher_win.py game_zip, latest_release, installable_releases)."""
from paths import ROOT
import io
import json
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(ROOT / 'launcher'))
sys.path.insert(0, str(ROOT / 'scripts'))
import bbport_launcher_win as L  # noqa: E402

GAME = {'name': L.update_package_name('9.9.9-tatsunakyo.1'), 'browser_download_url': 'https://example.invalid/game.zip'}
SOURCE = {'name': 'fsr4vk-v0.4.3-amdfix-src.zip', 'browser_download_url': 'https://example.invalid/src.zip'}


def answer(data):
    response = io.BytesIO(json.dumps(data).encode())
    response.__enter__ = lambda self=response: self
    response.__exit__ = lambda *a: None
    return response


class GameZipTests(unittest.TestCase):
    def test_the_game_zip_whatever_was_uploaded_first(self):
        # 1.9.3 and 1.9.4 carry the FSR 4 source archive beside the game: uploaded first, the old
        # rule (the first .zip) downloaded it and the update stopped.
        for assets in ([GAME, SOURCE], [SOURCE, GAME]):
            self.assertEqual(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'assets': assets})[1], GAME['browser_download_url'])

    def test_a_differently_named_package_beside_a_source_archive(self):
        package = {'name': L.update_package_name('9.9.9-tatsunakyo.1'), 'browser_download_url': 'https://example.invalid/p.zip'}
        self.assertEqual(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'assets': [SOURCE, package]})[1], package['browser_download_url'])

    def test_no_guess_between_two_packages_or_a_source_archive_alone(self):
        other = {'name': 'Something.zip', 'browser_download_url': 'https://example.invalid/s.zip'}
        third = {'name': 'Else.zip', 'browser_download_url': 'https://example.invalid/e.zip'}
        self.assertIsNone(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'assets': [other, third]})[1])
        self.assertIsNone(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'assets': [SOURCE]})[1])
        self.assertIsNone(L.parse_release({'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'assets': []})[1])

    def test_latest_release_offers_the_game_zip(self):
        release = {'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'html_url': 'https://example.invalid/r', 'assets': [SOURCE, GAME]}
        with mock.patch.object(L.bbport_tls, 'urlopen', return_value=answer(release)):
            self.assertEqual(L.latest_release(), ('9.9.9-tatsunakyo.1', GAME['browser_download_url'], 'https://example.invalid/r'))

    def test_other_versions_list_the_game_zips(self):
        releases = [{'tag_name': 'windows-v9.9.9-tatsunakyo.1', 'html_url': 'a', 'assets': [SOURCE, GAME]},
                    {'tag_name': 'windows-v1.9.7-tatsunakyo.55', 'html_url': 'b', 'assets': [{**GAME, 'name': L.update_package_name('1.9.7-tatsunakyo.55')}, SOURCE]}]
        with mock.patch.object(L.bbport_tls, 'urlopen', return_value=answer(releases)):
            found = L.installable_releases()
        self.assertEqual([(v, u) for v, u, _p in found],
                         [('9.9.9-tatsunakyo.1', GAME['browser_download_url']), ('1.9.7-tatsunakyo.55', GAME['browser_download_url'])])


if __name__ == '__main__':
    unittest.main()
