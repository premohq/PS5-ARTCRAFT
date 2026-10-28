import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from artcraft_ps5 import edition, releases
from artcraft_ps5.edition import Pin
from tests import fixtures

SUMS = '''\
1111111111111111111111111111111111111111111111111111111111111111  photocraft-0.16.0-windows-x64-portable.zip
2222222222222222222222222222222222222222222222222222222222222222 *photocraft-0.16.0-windows-x64-setup.msi
3333333333333333333333333333333333333333333333333333333333333333  photocraft-0.16.0-windows-arm64-portable.zip

4444444444444444444444444444444444444444444444444444444444444444  photocraft-0.16.0-macos-universal.dmg
'''


class Sums(unittest.TestCase):
    def test_parse(self):
        sums = releases.parse_sha256sums(SUMS)
        self.assertEqual(len(sums), 4)
        self.assertEqual(sums['photocraft-0.16.0-windows-x64-setup.msi'], '2' * 64)

    def test_parse_refuses_junk(self):
        with self.assertRaisesRegex(edition.EditionError, 'line 2'):
            releases.parse_sha256sums('1' * 64 + '  a.zip\nnot a checksum line\n')

    def test_portable_asset(self):
        sums = releases.parse_sha256sums(SUMS)
        self.assertEqual(releases.portable_asset(sums, 'photocraft'),
                         ('photocraft-0.16.0-windows-x64-portable.zip', '0.16.0'))
        self.assertEqual(releases.portable_asset(sums, 'photocraft', 'arm64')[1], '0.16.0')
        with self.assertRaisesRegex(edition.EditionError, 'found 0'):
            releases.portable_asset(sums, 'vectorcraft')


class Latest(unittest.TestCase):
    def test_latest_pin_and_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            directory = fixtures.make_edition(tmp / 'edition', tmp / 'downloads', apps=('photocraft',))
            e = edition.load(directory)
            files = {}
            for app in (e.launcher, *e.apps):
                asset = f'{app.id}-2.0.0-windows-x64-portable.zip'
                data = app.id.encode() * 100
                files[f'https://github.com/{app.repo}/releases/latest/download/SHA256SUMS.txt'] = \
                    f'{hashlib.sha256(data).hexdigest()}  {asset}\n'.encode()
                files[releases.asset_url(app.repo, 'v2.0.0', asset)] = data
            web = fixtures.Web(files)
            said = []
            lock = releases.refresh_lock(e, directory / 'suite.lock.json', web, say=said.append)
            self.assertEqual(lock['pins']['photocraft']['version'], '2.0.0')
            self.assertEqual(lock['pins']['photocraft']['size'], len(b'photocraft') * 100)
            self.assertIn('(was 1.2.3)', said[1])
            # only checksum lists and one-byte probes: no API call, no full download
            self.assertTrue(all(url.endswith('SHA256SUMS.txt') or wanted == 'bytes=0-0' for url, wanted in web.requests))
            self.assertEqual(edition.load(directory).pins['photocraft'].version, '2.0.0')
            self.assertEqual(json.loads((directory / 'suite.lock.json').read_text())['arch'], 'x64')


class Download(unittest.TestCase):
    data = bytes(range(256)) * 4096

    def pin(self):
        return Pin(id='photocraft', version='1.0.0', tag='v1.0.0', asset='photocraft.zip', url='https://x/photocraft.zip',
                   sha256=hashlib.sha256(self.data).hexdigest(), size=len(self.data))

    def test_download_then_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = fixtures.Web({'https://x/photocraft.zip': self.data})
            path = releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual(path.read_bytes(), self.data)
            releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual(len(web.requests), 1)

    def test_resumes_a_partial_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'photocraft.zip.part').write_bytes(self.data[:1000])
            web = fixtures.Web({'https://x/photocraft.zip': self.data})
            releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual(web.requests, [('https://x/photocraft.zip', 'bytes=1000-')])
            self.assertEqual((Path(tmp) / 'photocraft.zip').read_bytes(), self.data)

    def test_server_without_ranges_starts_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'photocraft.zip.part').write_bytes(b'stale' * 10)
            web = fixtures.Web({'https://x/photocraft.zip': self.data}, ranges=False)
            releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual((Path(tmp) / 'photocraft.zip').read_bytes(), self.data)

    def test_refuses_a_file_that_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = fixtures.Web({'https://x/photocraft.zip': self.data[::-1]})
            with self.assertRaisesRegex(edition.EditionError, 'the pin says'):
                releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_replaces_a_bad_cached_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'photocraft.zip').write_bytes(b'x' * len(self.data))
            web = fixtures.Web({'https://x/photocraft.zip': self.data})
            releases.download(self.pin(), Path(tmp), web, say=lambda _: None)
            self.assertEqual((Path(tmp) / 'photocraft.zip').read_bytes(), self.data)


if __name__ == '__main__':
    unittest.main()
