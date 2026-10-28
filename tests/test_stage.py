import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from artcraft_ps5 import edition, regfile, stage
from tests import fixtures

PREFIX = 'data/ps5proton/prefixes/artcraft/drive_c/ArtCraft'


class Stage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.downloads = tmp / 'downloads'
        self.edition = edition.load(fixtures.make_edition(tmp / 'edition', self.downloads), need_lock=True)
        self.session = tmp / 'artcraft-session.exe'
        self.session.write_bytes(fixtures.signed_pe(None, b'session'))
        self.wallpaper = tmp / 'wallpaper.bmp'
        self.wallpaper.write_bytes(b'BM wallpaper')
        self.out = tmp / 'out'

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self, **options):
        return stage.stage(self.edition, self.downloads, self.out, self.session, self.wallpaper, installed_at=1,
                           say=lambda _: None, **options)

    def test_layout(self):
        staged = self.stage()
        self.assertEqual(staged.apps, ('photocraft', 'gridcraft'))
        root = self.out / PREFIX
        self.assertTrue((root / 'Launcher' / 'artcraft-launcher.exe').is_file())
        self.assertTrue((root / 'Launcher' / 'portable.txt').is_file())
        self.assertTrue((root / 'Apps' / 'photocraft' / 'photocraft.exe').is_file())
        self.assertFalse((root / 'Apps' / 'photocraft' / 'photocraft-cli.exe').exists())
        self.assertEqual((root / 'System' / 'artcraft-session.exe').read_bytes(), self.session.read_bytes())
        self.assertEqual((root / 'Theme' / stage.WALLPAPER).read_bytes(), b'BM wallpaper')
        self.assertFalse((self.out / 'data/ps5proton/prefixes/artcraft/drive_c/windows').exists())

        game = json.loads((self.out / 'data/ps5proton/games/artcraft/game.json').read_text())
        self.assertEqual(game['arguments'], r'C:\ArtCraft\System\artcraft-session.exe')
        self.assertEqual(game['prefix'], 'artcraft')
        title = json.loads((self.out / 'data/homebrew/PPSA99170/edition.json').read_text())
        self.assertEqual(title['profile'], 'artcraft')

    def test_launcher_adopts_the_apps(self):
        self.stage()
        data = self.out / PREFIX / 'Launcher' / 'ArtCraftLauncherData' / 'data'
        installed = json.loads((data / 'installed.json').read_text())['apps']
        self.assertEqual(sorted(installed), ['gridcraft', 'photocraft'])
        record = installed['photocraft']
        self.assertEqual(record['installed_at'], 1)
        for file in record['files']:
            relative = file.removeprefix('C:\\ArtCraft\\').replace('\\', '/')
            self.assertTrue((self.out / PREFIX / relative).is_file(), file)
        self.assertIn('install_locations:(root:Some(', (data / 'app.ron').read_text())

    def test_trust_comes_from_the_launcher_signature(self):
        self.stage()
        text = (self.out / PREFIX / 'System' / 'trust.reg').read_bytes()[2:].decode('utf-16-le')
        thumbprint = hashlib.sha1(fixtures.ROOT_CERT).hexdigest().upper()
        self.assertIn(f'[{regfile.ROOT_STORE}\\{thumbprint}]', text)
        self.assertIn(f'"State"=dword:{regfile.WTPF_DEFAULT | regfile.WTPF_IGNOREEXPIRATION:08x}', text)

    def test_session_ini(self):
        self.stage()
        ini = (self.out / PREFIX / 'System' / 'session.ini').read_bytes().decode('ascii')
        self.assertIn('\r\n[environment]\r\nWGPU_BACKEND=vulkan\r\n', ini)
        self.assertIn(r'PhotoCraft=C:\ArtCraft\Apps\photocraft\photocraft.exe', ini)
        defaults = (self.out / PREFIX / 'System' / 'defaults.reg').read_bytes()
        self.assertIn(f'defaults_id={self.edition.version}-{hashlib.sha256(defaults).hexdigest()[:12]}', ini)

    def test_manifest(self):
        staged = self.stage()
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(len(manifest['files']), staged.files)
        for entry in manifest['files']:
            file = self.out / entry['path'].lstrip('/')
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), entry['sha256'])

    def test_options(self):
        self.stage(app_ids=['gridcraft'], include_cli=True)
        self.assertTrue((self.out / PREFIX / 'Apps' / 'gridcraft' / 'gridcraft-cli.exe').is_file())
        self.assertFalse((self.out / PREFIX / 'Apps' / 'photocraft').exists())

    def test_refusals(self):
        self.out.mkdir()
        (self.out / 'x').write_text('x')
        with self.assertRaisesRegex(edition.EditionError, 'not empty'):
            self.stage()
        (self.out / 'x').unlink()
        self.session.unlink()
        with self.assertRaisesRegex(edition.EditionError, 'make -C session'):
            self.stage()

    def test_a_missing_download_names_fetch(self):
        (self.downloads / self.edition.pins['gridcraft'].asset).unlink()
        with self.assertRaisesRegex(edition.EditionError, 'artcraft_ps5 fetch'):
            self.stage()

    def test_a_launcher_signed_by_someone_else(self):
        tmp = Path(self.tmp.name)
        directory = fixtures.make_edition(
            tmp / 'other', self.downloads,
            edit=lambda e: e['trust']['code_signing_roots'][0].update(sha256='AB' * 32, sha1='CD' * 20))
        self.edition = edition.load(directory, need_lock=True)
        with self.assertRaisesRegex(edition.EditionError, 'signing chain'):
            self.stage()


if __name__ == '__main__':
    unittest.main()
