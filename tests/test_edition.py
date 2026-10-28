import json
import tempfile
import unittest
from pathlib import Path, PureWindowsPath

from artcraft_ps5 import edition
from tests import fixtures


class RealEdition(unittest.TestCase):
    def test_loads_with_every_app_pinned(self):
        e = edition.load(need_lock=True)
        self.assertEqual(e.title_id, 'PPSA99170')
        self.assertEqual(len(e.apps), 13)
        self.assertEqual(set(e.pins), {e.launcher.id} | {a.id for a in e.apps})
        for pin in e.pins.values():
            self.assertTrue(pin.asset.startswith(f'{pin.id}-{pin.version}-windows-x64-portable'))
            self.assertIn(f'/releases/download/{pin.tag}/{pin.asset}', pin.url)

    def test_paths(self):
        e = edition.load()
        self.assertEqual(e.launcher_exe, PureWindowsPath(r'C:\ArtCraft\Launcher\artcraft-launcher.exe'))
        self.assertEqual(e.app_exe(e.app('photocraft')), PureWindowsPath(r'C:\ArtCraft\Apps\photocraft\photocraft.exe'))
        self.assertEqual(edition.windows_host_path(Path('/p'), e.launcher_exe),
                         Path('/p/drive_c/ArtCraft/Launcher/artcraft-launcher.exe'))
        with self.assertRaises(edition.EditionError):
            edition.windows_host_path(Path('/p'), PureWindowsPath(r'D:\x'))

    def test_chosen_apps(self):
        e = edition.load()
        self.assertEqual(e.chosen_apps(), e.apps)
        self.assertEqual([a.id for a in e.chosen_apps(['gridcraft'])], ['gridcraft'])
        with self.assertRaises(edition.EditionError):
            e.chosen_apps(['notcraft'])

    def test_app_colour(self):
        self.assertEqual(edition.load().app('photocraft').rgb, (0x2f, 0x7b, 0xf5))


class Validation(unittest.TestCase):
    def broken(self, change, file='edition.json', message=''):
        with tempfile.TemporaryDirectory() as tmp:
            directory = fixtures.copy_real_edition(Path(tmp) / 'edition')
            data = json.loads((directory / file).read_text())
            change(data)
            (directory / file).write_text(json.dumps(data))
            with self.assertRaisesRegex(edition.EditionError, message):
                edition.load(directory)

    def test_root_must_be_c_without_spaces(self):
        self.broken(lambda d: d.update(root=r'C:\Art Craft'), message='without spaces')
        self.broken(lambda d: d.update(root=r'D:\ArtCraft'), message='C:')

    def test_reserved_environment(self):
        self.broken(lambda d: d.update(environment=['PROTON_LOG=1']), message='reserved')
        self.broken(lambda d: d.update(environment=['not a word']), message='NAME=VALUE')

    def test_prefix_of_its_own(self):
        self.broken(lambda d: d['profile'].update(prefix='mihawk'), message='prefix of its own')

    def test_launcher_settings(self):
        self.broken(lambda d: d['launcher_settings'].update(check_every='Minute'), message='check_every')
        self.broken(lambda d: d['launcher_settings'].update(preferred_kinds=['Exe']), message='preferred_kinds')

    def test_title_id(self):
        self.broken(lambda d: d['title'].update(id='ARTCRAFT'), message='title id')

    def test_seed_names_known_apps(self):
        self.broken(lambda d: d['seed'].update(apps=['notcraft']), message='notcraft')

    def test_suite(self):
        self.broken(lambda d: d['apps'][0].update(color='blue'), 'suite.json', 'color')
        self.broken(lambda d: d['apps'][1].update(id=d['apps'][0]['id']), 'suite.json', 'unique')

    def test_lock(self):
        self.broken(lambda d: d['pins']['photocraft'].update(sha256='00'), 'suite.lock.json', 'sha256')
        self.broken(lambda d: d['pins']['photocraft'].update(url='http://x'), 'suite.lock.json', 'https')
        self.broken(lambda d: d['pins'].update(notcraft=d['pins']['photocraft']), 'suite.lock.json', 'notcraft')

    def test_missing_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = fixtures.copy_real_edition(Path(tmp) / 'edition')
            (directory / 'suite.lock.json').unlink()
            self.assertEqual(edition.load(directory).pins, {})
            with self.assertRaisesRegex(edition.EditionError, 'lock --refresh'):
                edition.load(directory, need_lock=True)


if __name__ == '__main__':
    unittest.main()
