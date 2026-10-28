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


def write_staged(folder: Path, files: dict[str, bytes]) -> Path:
    import hashlib
    entries = []
    for path, data in files.items():
        target = folder / path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append({'path': path, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    (folder / 'manifest.json').write_text(json.dumps({'edition': '0.1.0', 'prefix': PREFIX, 'apps': [], 'files': entries}))
    return folder


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
