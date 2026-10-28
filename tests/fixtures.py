"""Small stand-ins for what the tools read from outside: release ZIPs, a signed launcher, GitHub and ftpsrv."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import struct
import zipfile
from pathlib import Path

from artcraft_ps5 import ROOT

REAL_EDITION = ROOT / 'edition'


def der(tag: int, value: bytes) -> bytes:
    length = len(value)
    if length < 0x80:
        head = bytes([length])
    else:
        size = (length.bit_length() + 7) // 8
        head = bytes([0x80 | size]) + length.to_bytes(size, 'big')
    return bytes([tag]) + head + value


def certificate(name: str) -> bytes:
    """Not a real X.509 certificate: a DER SEQUENCE the signature carries, which is all the tools look at."""
    return der(0x30, der(0x0c, name.encode()) + der(0x04, hashlib.sha256(name.encode()).digest()))


def pkcs7(certificates: list[bytes]) -> bytes:
    signed = der(0x30, der(0x02, b'\x01') + der(0x31, b'') + der(0x30, der(0x06, bytes.fromhex('2a864886f70d010701')))
                 + der(0xa0, b''.join(certificates)) + der(0x31, b''))
    return der(0x30, der(0x06, bytes.fromhex('2a864886f70d010702')) + der(0xa0, signed))


def signed_pe(signature: bytes | None, body: bytes = b'program') -> bytes:
    """A PE32+ file whose security directory holds `signature` as a WIN_CERTIFICATE (or nothing, unsigned)."""
    pe = 0x40
    optional = pe + 24
    directories = optional + 112
    header = bytearray(directories + 16 * 8)
    header[:2] = b'MZ'
    struct.pack_into('<I', header, 0x3c, pe)
    header[pe:pe + 4] = b'PE\0\0'
    struct.pack_into('<H', header, optional, 0x20b)
    program = bytes(header) + body
    if signature is None:
        return program
    program += b'\0' * (-len(program) % 8)
    blob = struct.pack('<IHH', 8 + len(signature), 0x0200, 0x0002) + signature
    blob += b'\0' * (-len(blob) % 8)
    table = bytearray(program)
    struct.pack_into('<II', table, directories + 4 * 8, len(program), len(blob))
    return bytes(table) + blob


ROOT_CERT = certificate('Test Code Signing Root')
CHAIN = [certificate('Test Publisher'), certificate('Test Intermediate'), ROOT_CERT]


def portable_zip(path: Path, stem: str, version: str, files: dict[str, bytes], *, wrapper: bool = True) -> Path:
    """A release's portable ZIP, laid out as the suite's release script makes it (one version-named folder)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    folder = f'{stem}-{version}/' if wrapper else ''
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        if wrapper:
            archive.writestr(folder, b'')
        for name, data in files.items():
            archive.writestr(folder + name, data)
    return path


def app_files(app_id: str) -> dict[str, bytes]:
    return {f'{app_id}.exe': signed_pe(None, app_id.encode()), f'{app_id}-cli.exe': b'cli ' + app_id.encode(),
            'resources/fonts/font.ttf': b'font', 'LICENSE.txt': b'MIT'}


def launcher_files() -> dict[str, bytes]:
    return {'artcraft-launcher.exe': signed_pe(pkcs7(CHAIN)), 'portable.txt': b''}


def make_edition(directory: Path, downloads: Path, apps=('photocraft', 'gridcraft'), *, edit=None) -> Path:
    """An edition folder like edition/, with only `apps` in its suite, its trust root swapped for the test one,
    and a lock file pinning ZIPs made in `downloads`."""
    directory.mkdir(parents=True, exist_ok=True)
    edition = json.loads((REAL_EDITION / 'edition.json').read_text())
    edition['trust']['code_signing_roots'] = [{
        'subject': 'Test Code Signing Root',
        'sha1': hashlib.sha1(ROOT_CERT).hexdigest().upper(),
        'sha256': hashlib.sha256(ROOT_CERT).hexdigest().upper(),
        'source': 'tests/fixtures.py',
    }]
    if edit:
        edit(edition)
    suite = json.loads((REAL_EDITION / 'suite.json').read_text())
    suite['apps'] = [a for a in suite['apps'] if a['id'] in apps]
    (directory / 'edition.json').write_text(json.dumps(edition, indent=2))
    (directory / 'suite.json').write_text(json.dumps(suite, indent=2))
    pins = {}
    for app_id, files in [('artcraft-launcher', launcher_files())] + [(a, app_files(a)) for a in apps]:
        version = '1.2.3'
        asset = f'{app_id}-{version}-windows-x64-portable.zip'
        zip_path = portable_zip(downloads / asset, app_id, version, files)
        pins[app_id] = {'version': version, 'tag': f'v{version}', 'asset': asset,
                        'url': f'https://example.invalid/{asset}',
                        'sha256': hashlib.sha256(zip_path.read_bytes()).hexdigest(), 'size': zip_path.stat().st_size}
    (directory / 'suite.lock.json').write_text(json.dumps({'arch': 'x64', 'pins': pins}, indent=2))
    return directory


def copy_real_edition(directory: Path) -> Path:
    shutil.copytree(REAL_EDITION, directory)
    return directory


class Response(io.BytesIO):
    """What urllib.request.urlopen hands back, as far as the tools use it."""

    def __init__(self, data: bytes, status: int = 200, headers: dict | None = None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class Web:
    """An opener serving fixed files, honouring Range the way GitHub's release CDN does; it records each request."""

    def __init__(self, files: dict[str, bytes], *, ranges: bool = True):
        self.files = files
        self.ranges = ranges
        self.requests: list[tuple[str, str | None]] = []

    def __call__(self, request):
        url = request.full_url
        wanted = request.get_header('Range')
        self.requests.append((url, wanted))
        if url not in self.files:
            raise AssertionError(f'unexpected request for {url}')
        data = self.files[url]
        if wanted and self.ranges:
            first, _, last = wanted.removeprefix('bytes=').partition('-')
            end = int(last) + 1 if last else len(data)
            return Response(data[int(first):end], 206, {'Content-Range': f'bytes {first}-{end - 1}/{len(data)}'})
        return Response(data)


class FakeFTP:
    """ftpsrv as far as deploy.py talks to it: a dict of paths to bytes, with SELF on until it is toggled."""

    def __init__(self, files: dict[str, bytes] | None = None, *, self_on: bool = True):
        self.files = files if files is not None else {}
        self.dirs: set[str] = set()
        self.self_on = self_on
        self.stored: list[str] = []
        self.logged_in = False

    def __call__(self):
        return self

    def connect(self, host, port, timeout=None):
        self.address = (host, port)

    def login(self, user, password):
        self.logged_in = True

    def sendcmd(self, command):
        if command == 'SELF':
            self.self_on = not self.self_on
            return f'200 SELF decryption {"enabled" if self.self_on else "disabled"}'
        raise AssertionError(command)

    def mkd(self, path):
        import ftplib
        if path in self.dirs:
            raise ftplib.error_perm('550 exists')
        self.dirs.add(path)

    def storbinary(self, command, file, blocksize=8192):
        path = command.removeprefix('STOR ')
        self.files[path] = file.read()
        self.stored.append(path)

    def retrbinary(self, command, callback):
        import ftplib
        path = command.removeprefix('RETR ')
        if path not in self.files:
            raise ftplib.error_perm('550 no such file')
        callback(self.files[path])

    def delete(self, path):
        import ftplib
        if path not in self.files:
            raise ftplib.error_perm('550 no such file')
        del self.files[path]

    def rename(self, source, target):
        self.files[target] = self.files.pop(source)

    def quit(self):
        self.logged_in = False

    def close(self):
        self.logged_in = False
