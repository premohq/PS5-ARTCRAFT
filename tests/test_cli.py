import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artcraft_ps5 import cli
from tests import fixtures


def run(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.downloads = self.dir / 'downloads'
        self.edition = fixtures.make_edition(self.dir / 'edition', self.downloads)
        self.session = self.dir / 'artcraft-session.exe'
        self.session.write_bytes(b'MZ')

    def tearDown(self):
        self.tmp.cleanup()

    def test_show_the_real_edition(self):
        code, out, _ = run('show')
        self.assertEqual(code, 0)
        self.assertIn('title PPSA99278', out)
        self.assertIn('photocraft', out)

    def test_lock_lists_pins(self):
        code, out, _ = run('--edition', self.edition, 'lock')
        self.assertEqual(code, 0)
        self.assertIn('gridcraft          1.2.3', out)

    def test_lock_refresh_dry_run_writes_nothing(self):
        before = (self.edition / 'suite.lock.json').read_bytes()
        web = fixtures.newer_releases(self.edition, '2.0.0', keep=('gridcraft',))
        with mock.patch('urllib.request.urlopen', web):
            code, out, _ = run('--edition', self.edition, 'lock', '--refresh', '--dry-run')
        self.assertEqual(code, 0)
        self.assertIn('photocraft         2.0.0', out)
        self.assertIn('2 would change: artcraft-launcher, photocraft', out)
        self.assertEqual((self.edition / 'suite.lock.json').read_bytes(), before)

    def test_lock_dry_run_needs_refresh(self):
        code, _, err = run('--edition', self.edition, 'lock', '--dry-run')
        self.assertEqual(code, 1)
        self.assertIn('--refresh --dry-run', err)

    def test_show_reports_an_unpinned_app(self):
        lock = json.loads((self.edition / 'suite.lock.json').read_text())
        del lock['pins']['gridcraft']
        (self.edition / 'suite.lock.json').write_text(json.dumps(lock))
        code, out, _ = run('--edition', self.edition, 'show')
        self.assertEqual(code, 1)
        self.assertIn('not pinned: gridcraft', out)

    def test_errors_are_one_line(self):
        code, _, err = run('--edition', self.dir / 'nowhere', 'show')
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith('error: '))

    def test_build_stage_and_dry_run_deploy(self):
        out = self.dir / 'dist'
        wallpaper = self.dir / 'wall.bmp'
        args = ['--edition', self.edition, 'build', '--downloads', self.downloads, '--out', out,
                '--session-exe', self.session, '--wallpaper', wallpaper]
        drawn = []
        with mock.patch.object(cli, 'draw_wallpaper', lambda e, path, w, h: drawn.append(path) or
                               path.write_bytes(b'BM')), mock.patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '7'}):
            code, text, err = run(*args)
        self.assertEqual((code, err), (0, ''), text)
        self.assertEqual(drawn, [wallpaper])
        installed = out / 'data/artcraft/prefixes/artcraft/drive_c/ArtCraft/Launcher/ArtCraftLauncherData/data'
        self.assertEqual(json.loads((installed / 'installed.json').read_text())['apps']['photocraft']['installed_at'], 7)

        code, _, err = run(*args)
        self.assertEqual(code, 1)
        self.assertIn('not empty', err)
        with mock.patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '7'}):
            self.assertEqual(run(*args, '--clean')[0], 0)

        code, text, _ = run('--edition', self.edition, 'deploy', '--staged', out, '--dry-run')
        self.assertEqual(code, 0)
        self.assertIn('dry run: nothing sent', text)

    def test_clean_leaves_other_folders_alone(self):
        folder = self.dir / 'mine'
        folder.mkdir()
        (folder / 'keep.txt').write_text('keep')
        code, _, err = run('--edition', self.edition, 'stage', '--clean', '--out', folder, '--downloads',
                           self.downloads, '--session-exe', self.session, '--wallpaper', self.session)
        self.assertEqual(code, 1)
        self.assertIn('no manifest.json', err)
        self.assertTrue((folder / 'keep.txt').is_file())

    def test_deploy_needs_a_staged_edition(self):
        code, _, err = run('deploy', '--staged', self.dir, '--dry-run')
        self.assertEqual(code, 1)
        self.assertIn('artcraft_ps5 build', err)

    def test_artwork(self):
        code, _, _ = run('wallpaper', '--out', self.dir / 'w.png', '--width', 64, '--height', 36)
        self.assertEqual(code, 0)
        self.assertEqual((self.dir / 'w.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        code, _, _ = run('icon', '--out', self.dir / 'i.png', '--size', 32)
        self.assertEqual(code, 0)
        from PIL import Image
        with Image.open(self.dir / 'i.png') as image:
            self.assertEqual(image.size, (32, 32))

    def test_wallpaper_is_the_same_every_time(self):
        run('wallpaper', '--out', self.dir / 'a.bmp', '--width', 48, '--height', 27)
        run('wallpaper', '--out', self.dir / 'b.bmp', '--width', 48, '--height', 27)
        self.assertEqual((self.dir / 'a.bmp').read_bytes(), (self.dir / 'b.bmp').read_bytes())
        self.assertEqual((self.dir / 'a.bmp').read_bytes()[:2], b'BM')


if __name__ == '__main__':
    unittest.main()
