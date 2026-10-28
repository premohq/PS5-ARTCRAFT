import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from artcraft_ps5 import edition, portable
from tests import fixtures

APP = edition.App('photocraft', 'PhotoCraft', 'Image editing', 'storytold/photocraft', '#2f7bf5')
DESTINATION = PureWindowsPath(r'C:\ArtCraft\Apps\photocraft')


class Layout(unittest.TestCase):
    def layout(self, names):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                for name in names:
                    archive.writestr(name, b'' if name.endswith('/') else b'x')
            with zipfile.ZipFile(path) as archive:
                return portable.read_layout(archive, ('photocraft',))

    def test_wrapper_folder_is_flattened(self):
        layout = self.layout(['photocraft-1.0.0/', 'photocraft-1.0.0/photocraft.exe', 'photocraft-1.0.0/data/a.bin'])
        self.assertEqual(layout.executable, PurePosixPath('photocraft.exe'))
        self.assertEqual([str(r) for _, r in layout.files], ['photocraft.exe', 'data/a.bin'])

    def test_flat_zip(self):
        self.assertEqual(self.layout(['PhotoCraft.EXE', 'a.txt']).executable, PurePosixPath('PhotoCraft.EXE'))

    def test_refusals(self):
        for names, message in [
            (['../photocraft.exe'], 'unsafe'),
            (['a\\photocraft.exe'], 'unsafe'),
            (['photocraft.exe', 'PHOTOCRAFT.exe'], 'duplicate'),
            (['a/photocraft.exe', 'b/x.txt'], 'unsupported'),
            (['a/b/photocraft.exe'], 'expected executable'),
            (['a/'], 'no files'),
        ]:
            with self.subTest(names=names), self.assertRaisesRegex(edition.EditionError, message):
                self.layout(names)


class Install(unittest.TestCase):
    def test_install_records_every_file_and_leaves_cli_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = fixtures.portable_zip(Path(tmp) / 'p.zip', 'photocraft', '1.0.0', fixtures.app_files('photocraft'))
            out = Path(tmp) / 'out'
            record = portable.install(zip_path, APP, '1.0.0', DESTINATION, out, exclude=portable.is_cli(APP),
                                      installed_at=123)
            self.assertEqual(record['kind'], 'PortableZip')
            self.assertEqual(record['path'], r'C:\ArtCraft\Apps\photocraft\photocraft.exe')
            self.assertEqual(record['installed_at'], 123)
            self.assertEqual(sorted(record['files']), [r'C:\ArtCraft\Apps\photocraft\LICENSE.txt',
                                                       r'C:\ArtCraft\Apps\photocraft\photocraft.exe',
                                                       r'C:\ArtCraft\Apps\photocraft\resources\fonts\font.ttf'])
            self.assertFalse((out / 'photocraft-cli.exe').exists())
            self.assertTrue((out / 'resources' / 'fonts' / 'font.ttf').is_file())

    def test_folder_must_be_named_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = fixtures.portable_zip(Path(tmp) / 'p.zip', 'photocraft', '1.0.0', fixtures.app_files('photocraft'))
            with self.assertRaisesRegex(edition.EditionError, 'named photocraft'):
                portable.install(zip_path, APP, '1.0.0', PureWindowsPath(r'C:\Apps\PhotoCraft'), Path(tmp) / 'o')

    def test_executable_cannot_be_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = fixtures.portable_zip(Path(tmp) / 'p.zip', 'photocraft', '1.0.0', fixtures.app_files('photocraft'))
            with self.assertRaisesRegex(edition.EditionError, 'cannot be left out'):
                portable.install(zip_path, APP, '1.0.0', DESTINATION, Path(tmp) / 'o', exclude=lambda _: True)


if __name__ == '__main__':
    unittest.main()
