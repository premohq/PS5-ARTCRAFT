"""artcraft_ps5.deploy against a real FTP server on the loopback (pyftpdlib), standing in for the console's ftpsrv."""

import json
import socket
import threading
from pathlib import Path

import pytest

from artcraft_ps5 import deploy
from artcraft_ps5.edition import EditionError

pyftpdlib = pytest.importorskip('pyftpdlib')
from pyftpdlib.authorizers import DummyAuthorizer  # noqa: E402
from pyftpdlib.handlers import FTPHandler  # noqa: E402
from pyftpdlib.servers import FTPServer  # noqa: E402

PREFIX = '/data/ps5proton/prefixes/artcraft'


SEED = (f'{PREFIX}/drive_c/ArtCraft/Launcher/', f'{PREFIX}/drive_c/ArtCraft/Apps/')
LAUNCHER = f'{PREFIX}/drive_c/ArtCraft/Launcher/artcraft-launcher.exe'
INSTALLED = f'{PREFIX}/drive_c/ArtCraft/Launcher/ArtCraftLauncherData/data/installed.json'
SESSION = f'{PREFIX}/drive_c/ArtCraft/System/artcraft-session.exe'


def write_staged(folder: Path, files: dict[str, bytes], apps: tuple[str, ...] = ()) -> Path:
    import hashlib
    entries = []
    for path, data in files.items():
        target = folder / path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append({'path': path, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        if path.startswith(SEED):
            entries[-1]['seed'] = True
    manifest = {'edition': '0.1.0', 'prefix': PREFIX, 'apps': list(apps), 'files': entries}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    return folder


def on_console(root: Path, path: str) -> Path:
    return root / path.lstrip('/')


@pytest.fixture
def console(tmp_path):
    root = tmp_path / 'console'
    root.mkdir()
    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(root), perm='elradfmwMT')
    handler = type('Handler', (FTPHandler,), {'authorizer': authorizer, 'passive_ports': None})
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    server = FTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'timeout': 0.2}, daemon=True)
    thread.start()
    yield root, deploy.Console('127.0.0.1', port)
    server.close_all()


def test_send_then_send_only_what_changed(tmp_path, console):
    root, address = console
    files = {f'{PREFIX}/drive_c/ArtCraft/a.txt': b'one', f'{PREFIX}/drive_c/ArtCraft/Apps/x/x.exe': b'MZ',
             '/data/ps5proton/games/artcraft/game.json': b'{}'}
    staged = write_staged(tmp_path / 'dist', files)
    sent = deploy.deploy(staged, address, say=lambda *a: None)
    assert len(sent) == 3
    for path, data in files.items():
        assert (root / path.lstrip('/')).read_bytes() == data
    assert not list(root.rglob('.*.upload'))
    assert len(json.loads((root / PREFIX.lstrip('/') / deploy.REMOTE_MANIFEST).read_text())['files']) == 3
    assert deploy.deploy(staged, address, say=lambda *a: None) == []
    files[f'{PREFIX}/drive_c/ArtCraft/a.txt'] = b'two'
    staged = write_staged(tmp_path / 'dist', files)
    sent = deploy.deploy(staged, address, say=lambda *a: None)
    assert [e['path'] for e in sent] == [f'{PREFIX}/drive_c/ArtCraft/a.txt']
    assert (root / PREFIX.lstrip('/') / 'drive_c/ArtCraft/a.txt').read_bytes() == b'two'
    assert len(deploy.deploy(staged, address, force=True, say=lambda *a: None)) == 3


def test_dry_run_connects_to_nothing(tmp_path):
    staged = write_staged(tmp_path / 'dist', {f'{PREFIX}/drive_c/ArtCraft/a.txt': b'x'})
    lines = []
    assert len(deploy.deploy(staged, None, dry_run=True, say=lines.append)) == 1
    assert 'nothing sent' in lines[-1]


def test_windows_is_never_written(tmp_path):
    staged = write_staged(tmp_path / 'dist', {f'{PREFIX}/drive_c/windows/system32/x.dll': b'x'})
    with pytest.raises(EditionError, match='wineboot'):
        deploy.plan(staged, {})


def test_settings_come_from_the_env_file_and_the_address_is_masked(tmp_path):
    env = tmp_path / '.env'
    env.write_text('# the console\nPS5_HOST=192.168.1.23\nexport FTP_PORT="2121"\n')
    console = deploy.console_settings(env_file=env, environ={})
    assert (console.host, console.port) == ('192.168.1.23', 2121)
    assert console.masked == '192.*.*.23:2121'
    assert deploy.console_settings(env_file=env, environ={'PS5_HOST': '10.0.0.9'}).host == '10.0.0.9'
    with pytest.raises(EditionError, match='PS5_HOST'):
        deploy.console_settings(env_file=tmp_path / 'none', environ={})


def test_the_launcher_owns_the_launcher_and_the_apps_once_they_are_on_the_console(tmp_path, console):
    root, address = console
    app = f'{PREFIX}/drive_c/ArtCraft/Apps/photocraft/photocraft.exe'
    files = {LAUNCHER: b'launcher 0.8.1', INSTALLED: b'{"apps": 0.16}', app: b'photocraft 0.16', SESSION: b'session 1'}
    staged = write_staged(tmp_path / 'dist', files, apps=('photocraft',))
    assert len(deploy.deploy(staged, address, say=lambda *a: None)) == 4
    assert json.loads(on_console(root, f'{PREFIX}/{deploy.REMOTE_MANIFEST}').read_text())['seeded'] is True
    # On the console the launcher updates itself and PhotoCraft; on the PC the pins move and the helper changes.
    on_console(root, LAUNCHER).write_bytes(b'launcher 0.9.0')
    on_console(root, app).write_bytes(b'photocraft 0.17')
    on_console(root, INSTALLED).write_bytes(b'{"apps": 0.17}')
    files.update({LAUNCHER: b'launcher 0.8.2', INSTALLED: b'{"apps": 0.16, "at": 2}', app: b'photocraft 0.16.1',
                  SESSION: b'session 2'})
    staged = write_staged(tmp_path / 'dist2', files, apps=('photocraft',))
    lines = []
    assert [e['path'] for e in deploy.deploy(staged, address, say=lines.append)] == [SESSION]
    assert on_console(root, LAUNCHER).read_bytes() == b'launcher 0.9.0'
    assert on_console(root, app).read_bytes() == b'photocraft 0.17'
    assert on_console(root, INSTALLED).read_bytes() == b'{"apps": 0.17}'
    assert on_console(root, SESSION).read_bytes() == b'session 2'
    assert any('3 launcher and app files left' in line for line in lines)
    assert len(deploy.deploy(staged, address, force=True, say=lambda *a: None)) == 4
    assert on_console(root, LAUNCHER).read_bytes() == b'launcher 0.8.2'


def test_a_cut_seed_resumes_and_apps_staged_later_are_the_launchers_to_install(tmp_path, console):
    root, address = console
    app = f'{PREFIX}/drive_c/ArtCraft/Apps/soundcraft/soundcraft.exe'
    files = {LAUNCHER: b'launcher', app: b'soundcraft', SESSION: b'session'}
    staged = write_staged(tmp_path / 'dist', files, apps=('soundcraft',))
    # A transfer cut after the launcher: the console's manifest holds it, not yet the seed.
    remote = on_console(root, f'{PREFIX}/{deploy.REMOTE_MANIFEST}')
    remote.parent.mkdir(parents=True)
    digests = {e['path']: e['sha256'] for e in json.loads((staged / 'manifest.json').read_text())['files']}
    remote.write_text(json.dumps({'edition': '0.1.0', 'seeded': False, 'files': {LAUNCHER: digests[LAUNCHER]}}))
    assert sorted(e['path'] for e in deploy.deploy(staged, address, say=lambda *a: None)) == sorted([app, SESSION])
    later = f'{PREFIX}/drive_c/ArtCraft/Apps/gridcraft/gridcraft.exe'
    staged = write_staged(tmp_path / 'dist2', {**files, later: b'gridcraft'}, apps=('soundcraft', 'gridcraft'))
    lines = []
    assert deploy.deploy(staged, address, say=lines.append) == []
    assert not on_console(root, later).exists()
    assert any('seeded without them: gridcraft' in line for line in lines)
