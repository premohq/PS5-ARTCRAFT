"""Fixtures that stand in for the real releases: ZIPs laid out as the Craft apps' portable ZIPs are, and a minimal PE
whose Authenticode slot holds a PKCS#7 with a throwaway certificate (made with openssl), so no test downloads or runs
anything."""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def portable_zip(path: Path, app_id: str, version: str, *, wrapper: bool = True, extra: dict | None = None) -> Path:
    """A ZIP as `<app>-<version>-windows-x64-portable.zip` is: the exe, the CLI, licences and portable.txt in one
    version-named folder (or flat)."""
    files = {f'{app_id}.exe': b'MZ' + app_id.encode(), f'{app_id}-cli.exe': b'MZcli', 'LICENSE-MIT': b'mit',
             'portable.txt': b'portable', 'licenses/fonts/OFL.txt': b'ofl', **(extra or {})}
    prefix = f'{app_id}-{version}-windows-x64-portable/' if wrapper else ''
    with zipfile.ZipFile(path, 'w') as archive:
        if wrapper:
            archive.writestr(prefix, b'')
        for name, data in files.items():
            archive.writestr(prefix + name, data)
    return path


def minimal_pe(signature: bytes | None) -> bytes:
    """An MZ/PE32+ header, its data directories, and the PKCS#7 in a WIN_CERTIFICATE (type 2) after them."""
    pe_offset, optional_size = 0x40, 240
    body = bytearray(pe_offset + 4 + 20 + optional_size)
    body[0:2] = b'MZ'
    struct.pack_into('<I', body, 0x3c, pe_offset)
    body[pe_offset:pe_offset + 4] = b'PE\0\0'
    struct.pack_into('<HH', body, pe_offset + 4, 0x8664, 0)
    struct.pack_into('<H', body, pe_offset + 4 + 16, optional_size)
    optional = pe_offset + 24
    struct.pack_into('<H', body, optional, 0x20b)
    if signature is not None:
        offset = len(body) + (-len(body) % 8)
        body.extend(b'\0' * (offset - len(body)))
        blob = struct.pack('<IHH', 8 + len(signature), 0x0200, 2) + signature
        struct.pack_into('<II', body, optional + 112 + 4 * 8, offset, len(blob))
        body.extend(blob)
    return bytes(body)


@pytest.fixture(scope='session')
def signed_root(tmp_path_factory):
    """(DER of a throwaway root certificate, a PKCS#7 SignedData carrying it), or a skip without openssl."""
    if not shutil.which('openssl'):
        pytest.skip('openssl is not installed')
    folder = tmp_path_factory.mktemp('pki')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes',
                    '-keyout', str(folder / 'key.pem'), '-out', str(folder / 'root.pem'), '-subj', '/CN=Test Root',
                    '-days', '2'], check=True, capture_output=True)
    subprocess.run(['openssl', 'x509', '-in', str(folder / 'root.pem'), '-outform', 'DER', '-out',
                    str(folder / 'root.der')], check=True, capture_output=True)
    subprocess.run(['openssl', 'crl2pkcs7', '-nocrl', '-certfile', str(folder / 'root.pem'), '-outform', 'DER', '-out',
                    str(folder / 'p7.der')], check=True, capture_output=True)
    return (folder / 'root.der').read_bytes(), (folder / 'p7.der').read_bytes()
