"""artcraft_ps5.stage end to end on stand-in releases: what lands where on the console, and what each file says."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from artcraft_ps5 import edition as edition_module
from artcraft_ps5 import stage
from artcraft_ps5.edition import EditionError
from conftest import minimal_pe, portable_zip

ROOT = Path(__file__).resolve().parents[1]
PREFIX = Path('data/ps5proton/prefixes/artcraft/drive_c/ArtCraft')


@pytest.fixture
def staged(tmp_path, signed_root):
    root_der, pkcs7 = signed_root
    folder = tmp_path / 'edition'
    folder.mkdir()
    shutil.copy(ROOT / 'edition' / 'suite.json', folder)
    config = json.loads((ROOT / 'edition' / 'edition.json').read_text())
    config['seed']['apps'] = ['photocraft', 'gridcraft']
    config['trust']['code_signing_roots'] = [{'subject': 'Test Root', 'sha1': hashlib.sha1(root_der).hexdigest().upper(),
                                              'sha256': hashlib.sha256(root_der).hexdigest().upper()}]
    (folder / 'edition.json').write_text(json.dumps(config))
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    pins = {}
    for app_id, version in (('artcraft-launcher', '0.8.1'), ('photocraft', '0.16.0'), ('gridcraft', '0.12.1')):
        asset = f'{app_id}-{version}-windows-x64-portable.zip'
        extra = {f'{app_id}.exe': minimal_pe(pkcs7)} if app_id == 'artcraft-launcher' else None
        portable_zip(downloads / asset, app_id, version, extra=extra)
        data = (downloads / asset).read_bytes()
        pins[app_id] = {'version': version, 'tag': f'v{version}', 'asset': asset, 'url': f'https://example.invalid/{asset}',
                        'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
    (folder / 'suite.lock.json').write_text(json.dumps({'pins': pins}))
    session = tmp_path / 'artcraft-session.exe'
    session.write_bytes(b'MZsession')
    wallpaper = tmp_path / 'wall.bmp'
    wallpaper.write_bytes(b'BMwallpaper')
    edition = edition_module.load(folder, need_lock=True)
    out = tmp_path / 'dist'
    result = stage.stage(edition, downloads, out, session, wallpaper, installed_at=99, say=lambda *a: None)
    return edition, out, result, root_der


def test_the_console_paths(staged):
    _, out, result, _ = staged
    assert (out / PREFIX / 'Launcher' / 'artcraft-launcher.exe').is_file()
    assert (out / PREFIX / 'Launcher' / 'portable.txt').is_file()
    assert (out / PREFIX / 'Apps' / 'photocraft' / 'photocraft.exe').is_file()
    assert not (out / PREFIX / 'Apps' / 'photocraft' / 'photocraft-cli.exe').exists()
    assert (out / PREFIX / 'System' / 'artcraft-session.exe').read_bytes() == b'MZsession'
    assert (out / PREFIX / 'Theme' / 'artcraft-wallpaper.bmp').read_bytes() == b'BMwallpaper'
    assert not (out / 'data/ps5proton/prefixes/artcraft/drive_c/windows').exists()
    assert result.apps == ('photocraft', 'gridcraft')


def test_the_library_entry_starts_the_desktop_session_with_the_helper(staged):
    _, out, _, _ = staged
    entry = json.loads((out / 'data/ps5proton/games/artcraft/game.json').read_text())
    assert entry['executable'] == r'C:\windows\system32\mihawk.exe'
    assert entry['arguments'] == r'C:\ArtCraft\System\artcraft-session.exe' and ' ' not in entry['arguments']
    assert entry['prefix'] == 'artcraft' and entry['desktop'] is False and 'MIHAWK_DESKTOP=1' in entry['env']
    title = json.loads((out / 'data/homebrew/PPSA99170/edition.json').read_text())
    assert title == {'name': 'ArtCraft', 'profile': 'artcraft', 'hide_mihawk_desktop': True, 'browser_shortcut': False}


def test_the_launcher_owns_the_seeded_apps(staged):
    _, out, _, _ = staged
    data = out / PREFIX / 'Launcher' / 'ArtCraftLauncherData' / 'data'
    manifest = json.loads((data / 'installed.json').read_text())
    assert sorted(manifest['apps']) == ['gridcraft', 'photocraft']
    record = manifest['apps']['gridcraft']
    assert record['path'] == r'C:\ArtCraft\Apps\gridcraft\gridcraft.exe' and record['installed_at'] == 99
    assert all(f.startswith('C:\\ArtCraft\\Apps\\gridcraft\\') for f in record['files'])
    assert 'preferred_kinds:[PortableZip]' in (data / 'app.ron').read_text()


def test_trust_and_defaults_for_regedit(staged):
    _, out, _, root_der = staged
    trust = (out / PREFIX / 'System' / 'trust.reg').read_bytes()[2:].decode('utf-16-le')
    assert hashlib.sha1(root_der).hexdigest().upper() in trust
    assert '"State"=dword:00023d00' in trust
    defaults = (out / PREFIX / 'System' / 'defaults.reg').read_bytes()[2:].decode('utf-16-le')
    assert '"Wallpaper"="C:\\\\ArtCraft\\\\Theme\\\\artcraft-wallpaper.bmp"' in defaults
    pins = 'C:\\windows\\explorer.exe\0C:\\users\\Public\\Desktop\\ArtCraft Launcher.lnk\0'
    assert ','.join(f'{b:02x}' for b in pins.encode('utf-16-le')) in defaults.replace(',\\\r\n  ', ',')


def test_session_ini_names_every_suite_program_and_the_environment(staged):
    edition, out, _, _ = staged
    ini = (out / PREFIX / 'System' / 'session.ini').read_bytes().decode('ascii')
    assert 'launcher=C:\\ArtCraft\\Launcher\\artcraft-launcher.exe\r\n' in ini
    assert '[environment]\r\nWGPU_BACKEND=vulkan\r\n' in ini
    assert all(f'{app.name}=C:\\ArtCraft\\Apps\\{app.id}\\{app.id}.exe' in ini for app in edition.apps)
    assert 'defaults_id=0.1.0-' in ini


def test_the_manifest_lists_every_file_with_its_digest(staged):
    _, out, result, _ = staged
    manifest = json.loads((out / 'manifest.json').read_text())
    assert len(manifest['files']) == result.files
    for entry in manifest['files']:
        assert hashlib.sha256((out / entry['path'].lstrip('/')).read_bytes()).hexdigest() == entry['sha256']


def test_staging_refuses_a_used_folder_and_a_missing_helper(staged, tmp_path):
    edition, out, _, _ = staged
    with pytest.raises(EditionError, match='not empty'):
        stage.stage(edition, tmp_path, out, tmp_path / 'x.exe', tmp_path / 'w.bmp', say=lambda *a: None)
    with pytest.raises(EditionError, match='make -C session'):
        stage.stage(edition, tmp_path, tmp_path / 'fresh', tmp_path / 'missing.exe', tmp_path / 'w.bmp')
