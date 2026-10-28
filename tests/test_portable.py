"""artcraft_ps5.portable against the launcher's own rules (craft-launcher crates/native/src/portable.rs)."""

import zipfile
from pathlib import PureWindowsPath

import pytest

from artcraft_ps5 import portable
from artcraft_ps5.edition import App, EditionError
from tests.conftest import portable_zip

APP = App('photocraft', 'PhotoCraft', 'Image editing', 'storytold/photocraft', '#2f7bf5')
DEST = PureWindowsPath(r'C:\ArtCraft\Apps\photocraft')


def test_a_wrapped_zip_installs_flat_and_records_every_file(tmp_path):
    zip_path = portable_zip(tmp_path / 'p.zip', 'photocraft', '0.16.0')
    record = portable.install(zip_path, APP, '0.16.0', DEST, tmp_path / 'out', installed_at=7)
    assert record == {
        'version': '0.16.0', 'kind': 'PortableZip', 'path': r'C:\ArtCraft\Apps\photocraft\photocraft.exe',
        'installed_at': 7, 'needs_root': False,
        'files': [r'C:\ArtCraft\Apps\photocraft\photocraft.exe', r'C:\ArtCraft\Apps\photocraft\photocraft-cli.exe',
                  r'C:\ArtCraft\Apps\photocraft\LICENSE-MIT', r'C:\ArtCraft\Apps\photocraft\portable.txt',
                  r'C:\ArtCraft\Apps\photocraft\licenses\fonts\OFL.txt'],
    }
    assert (tmp_path / 'out' / 'photocraft.exe').read_bytes() == b'MZphotocraft'
    assert (tmp_path / 'out' / 'licenses' / 'fonts' / 'OFL.txt').read_bytes() == b'ofl'


def test_a_flat_zip_installs_as_it_is(tmp_path):
    zip_path = portable_zip(tmp_path / 'p.zip', 'photocraft', '0.16.0', wrapper=False)
    record = portable.install(zip_path, APP, '0.16.0', DEST, tmp_path / 'out')
    assert record['path'] == r'C:\ArtCraft\Apps\photocraft\photocraft.exe' and len(record['files']) == 5


def test_the_cli_left_out_is_not_recorded(tmp_path):
    zip_path = portable_zip(tmp_path / 'p.zip', 'photocraft', '0.16.0')
    record = portable.install(zip_path, APP, '0.16.0', DEST, tmp_path / 'out', exclude=portable.is_cli(APP))
    assert r'C:\ArtCraft\Apps\photocraft\photocraft-cli.exe' not in record['files']
    assert not (tmp_path / 'out' / 'photocraft-cli.exe').exists() and len(record['files']) == 4


def test_the_folder_must_be_named_by_the_app(tmp_path):
    zip_path = portable_zip(tmp_path / 'p.zip', 'photocraft', '0.16.0')
    with pytest.raises(EditionError, match='named photocraft'):
        portable.install(zip_path, APP, '0.16.0', PureWindowsPath(r'C:\ArtCraft\Apps\PhotoCraft2'), tmp_path / 'o')


@pytest.mark.parametrize('names, message', [
    (['../evil.exe'], 'unsafe path'),
    (['a\\b.exe'], 'unsafe path'),
    (['C:/x.exe'], 'unsafe path'),
    (['w/photocraft.exe', 'w/PHOTOCRAFT.EXE'], 'duplicate'),
    (['w/photocraft.exe', 'other/readme'], 'unsupported directory layout'),
    (['w/readme.txt'], 'expected executable'),
    (['w/x/photocraft.exe'], 'expected executable'),
])
def test_unsafe_or_odd_zips_are_refused(tmp_path, names, message):
    zip_path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(zip_path, 'w') as archive:
        for name in names:
            archive.writestr(name, b'x')
    with pytest.raises(EditionError, match=message):
        portable.install(zip_path, APP, '1.0.0', DEST, tmp_path / 'out')


def test_a_link_in_the_zip_is_refused(tmp_path):
    zip_path = tmp_path / 'link.zip'
    with zipfile.ZipFile(zip_path, 'w') as archive:
        archive.writestr('photocraft.exe', b'MZ')
        info = zipfile.ZipInfo('evil')
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        archive.writestr(info, '/etc/passwd')
    with pytest.raises(EditionError, match='link'):
        portable.install(zip_path, APP, '1.0.0', DEST, tmp_path / 'out')


def test_the_launcher_folder_unpacks_flat(tmp_path):
    zip_path = portable_zip(tmp_path / 'l.zip', 'artcraft-launcher', '0.8.1')
    exe = portable.unpack_folder(zip_path, ('artcraft-launcher',), tmp_path / 'Launcher')
    assert str(exe) == 'artcraft-launcher.exe' and (tmp_path / 'Launcher' / 'portable.txt').is_file()
