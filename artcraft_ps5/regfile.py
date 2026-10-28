"""A registry file for `regedit /S` (Windows Registry Editor Version 5.00, UTF-16LE), and the values the edition sets.

What each value does, and where Wine or the Mihawk shell reads it:

  HKCU\\Control Panel\\Desktop  Wallpaper           the desktop picture (wine/ps5/pw_shell_wallpaper.h keeps a
  HKCU\\Software\\MihawkOS      WallpaperInitialized  nonempty choice; 1 = never replace it with proton.bmp)
  HKCU\\Software\\Mihawk\\Shell  StartPins            Start's pinned apps, paths (wine/ps5/pw_shell_start.c)
                                BrowserPinned         1: never pin MihawkBrowser
  HKCU\\Software\\Microsoft\\SystemCertificates\\Root\\Certificates\\<SHA-1>  Blob
                                                     a trusted root (crypt32's registry store: the key is the
                                                     certificate's SHA-1 in uppercase hex, the blob its serialized
                                                     element, property 32 = CERT_CERT_PROP_ID holding the DER).
                                                     The user's store, not the machine's (HKLM): Wine 9.0's crypt32
                                                     deletes a root there that the host lacks the first time a
                                                     process opens the Root store, before any chain is built. Wine
                                                     9.0 and 11.0 both keep the user's copy, and their chain engine
                                                     trusts it (CertGetCertificateChain on HCCE_CURRENT_USER).
  HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Wintrust\\Trust Providers\\Software Publishing  State
                                                     WinVerifyTrust's policy flags (wintrust_main.c
                                                     WintrustGetRegPolicyFlags; Wine's default when absent is
                                                     WTPF_DEFAULT below)
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

# wintrust.h
WTPF_IGNOREEXPIRATION = 0x00000100
WTPF_OFFLINEOK_IND = 0x00000400
WTPF_OFFLINEOK_COM = 0x00000800
WTPF_OFFLINEOKNBU_IND = 0x00001000
WTPF_OFFLINEOKNBU_COM = 0x00002000
WTPF_IGNOREREVOCATIONONTS = 0x00020000
WTPF_DEFAULT = (WTPF_IGNOREREVOCATIONONTS | WTPF_OFFLINEOKNBU_COM | WTPF_OFFLINEOKNBU_IND
                | WTPF_OFFLINEOK_COM | WTPF_OFFLINEOK_IND)
CERT_CERT_PROP_ID = 32

ROOT_STORE = r'HKEY_CURRENT_USER\Software\Microsoft\SystemCertificates\Root\Certificates'
SOFTWARE_PUBLISHING = (r'HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Wintrust\Trust Providers'
                       r'\Software Publishing')


@dataclass
class RegFile:
    keys: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def _put(self, key: str, name: str, data: str) -> None:
        if not key.startswith(('HKEY_CURRENT_USER\\', 'HKEY_LOCAL_MACHINE\\')):
            raise ValueError(f'{key}: not under HKCU or HKLM')
        values = self.keys.setdefault(key, [])
        values[:] = [(n, d) for n, d in values if n != name]
        values.append((name, data))

    def string(self, key: str, name: str, value: str) -> None:
        self._put(key, name, '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"')

    def dword(self, key: str, name: str, value: int) -> None:
        self._put(key, name, f'dword:{value:08x}')

    def multi_string(self, key: str, name: str, values: list[str]) -> None:
        data = b''.join(v.encode('utf-16-le') + b'\0\0' for v in values) + b'\0\0'
        self._put(key, name, 'hex(7):' + _hex(data))

    def binary(self, key: str, name: str, data: bytes) -> None:
        self._put(key, name, 'hex:' + _hex(data))

    def text(self) -> str:
        lines = ['Windows Registry Editor Version 5.00', '']
        for key, values in self.keys.items():
            lines.append(f'[{key}]')
            lines.extend(f'"{name}"={data}' for name, data in values)
            lines.append('')
        return '\r\n'.join(lines) + '\r\n'

    def encoded(self) -> bytes:
        return b'\xff\xfe' + self.text().encode('utf-16-le')


def _hex(data: bytes, width: int = 25) -> str:
    """Comma-separated bytes, continued across lines the way regedit writes them."""
    pairs = [f'{b:02x}' for b in data]
    rows = [','.join(pairs[i:i + width]) for i in range(0, len(pairs), width)]
    return ',\\\r\n  '.join(rows)


def certificate_blob(der: bytes) -> bytes:
    """crypt32's serialized certificate element: one property header (id, 1, size) and the encoded certificate."""
    return struct.pack('<III', CERT_CERT_PROP_ID, 1, len(der)) + der


def trust_root(reg: RegFile, der: bytes) -> str:
    """Add a root certificate to the user's Root store; returns its key name (uppercase SHA-1)."""
    thumbprint = hashlib.sha1(der).hexdigest().upper()
    reg.binary(f'{ROOT_STORE}\\{thumbprint}', 'Blob', certificate_blob(der))
    return thumbprint
