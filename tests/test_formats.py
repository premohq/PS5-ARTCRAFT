"""The files the edition writes for others to read: the launcher's (installed.json, app.ron), regedit's (.reg) and
crypt32's (a certificate blob), and the certificates read out of a signature."""

import hashlib
import json
import struct
from pathlib import PureWindowsPath

import pytest

from artcraft_ps5 import authenticode, launcher_state, regfile
from artcraft_ps5.edition import EditionError
from conftest import minimal_pe


def test_ron_strings_escape_like_rust():
    assert launcher_state.ron_string('C:\\A "b"\n') == r'"C:\\A \"b\"\n"'


def test_app_ron_is_eframes_map_holding_the_settings():
    text = launcher_state.app_ron({'auto_update': True, 'notify': True, 'close_to_tray': False, 'check_every': 'Hour',
                                   'preferred_kinds': ['PortableZip']}, PureWindowsPath(r'C:\ArtCraft\Apps'))
    assert text == ('{\n    "settings": "(install_locations:(root:Some(\\"C:\\\\\\\\ArtCraft\\\\\\\\Apps\\"),per_app:{}),'
                    'auto_update:true,notify:true,close_to_tray:false,check_every:Hour,preferred_kinds:[PortableZip])",\n}\n')


def test_installed_json_is_the_launchers_manifest():
    record = {'version': '1.0.0', 'kind': 'PortableZip', 'path': 'C:\\x\\a.exe', 'installed_at': 1, 'files': [],
              'needs_root': False}
    manifest = json.loads(launcher_state.installed_json({'b': record, 'a': record}))
    assert list(manifest) == ['apps'] and list(manifest['apps']) == ['a', 'b']


def test_reg_file_is_utf16_with_regedit_syntax():
    reg = regfile.RegFile()
    reg.string(r'HKEY_CURRENT_USER\Control Panel\Desktop', 'Wallpaper', 'C:\\Art "x"')
    reg.dword(r'HKEY_CURRENT_USER\Software\Mihawk\Shell', 'BrowserPinned', 1)
    reg.multi_string(r'HKEY_CURRENT_USER\Software\Mihawk\Shell', 'StartPins', ['A', 'B'])
    data = reg.encoded()
    assert data[:2] == b'\xff\xfe'
    text = data[2:].decode('utf-16-le')
    assert text.startswith('Windows Registry Editor Version 5.00\r\n\r\n[HKEY_CURRENT_USER\\Control Panel\\Desktop]\r\n')
    assert '"Wallpaper"="C:\\\\Art \\"x\\""\r\n' in text
    assert '"BrowserPinned"=dword:00000001\r\n' in text
    assert '"StartPins"=hex(7):41,00,00,00,42,00,00,00,00,00\r\n' in text


def test_reg_values_replace_and_keys_stay_under_hkcu_or_hklm():
    reg = regfile.RegFile()
    reg.dword(r'HKEY_CURRENT_USER\K', 'V', 1)
    reg.dword(r'HKEY_CURRENT_USER\K', 'V', 2)
    assert reg.keys[r'HKEY_CURRENT_USER\K'] == [('V', 'dword:00000002')]
    with pytest.raises(ValueError):
        reg.dword(r'HKEY_USERS\K', 'V', 1)


def test_long_binary_values_wrap_as_regedit_writes_them():
    reg = regfile.RegFile()
    reg.binary(r'HKEY_LOCAL_MACHINE\K', 'Blob', bytes(range(30)))
    value = reg.keys[r'HKEY_LOCAL_MACHINE\K'][0][1]
    assert value.startswith('hex:00,01,') and ',\\\r\n  19,' in value


def test_a_trusted_root_is_its_serialized_element_under_its_sha1():
    der = b'0\x82\x00\x10certificate-bytes'
    reg = regfile.RegFile()
    thumbprint = regfile.trust_root(reg, der)
    assert thumbprint == hashlib.sha1(der).hexdigest().upper()
    key = regfile.ROOT_STORE + '\\' + thumbprint
    assert reg.keys[key][0][0] == 'Blob'
    assert regfile.certificate_blob(der) == struct.pack('<III', 32, 1, len(der)) + der


def test_wintrust_state_ignores_expiry_on_top_of_wines_default():
    assert regfile.WTPF_DEFAULT == 0x23C00
    assert regfile.WTPF_DEFAULT | regfile.WTPF_IGNOREEXPIRATION == 0x23D00


def test_certificates_come_out_of_a_signed_program(signed_root):
    root, pkcs7 = signed_root
    program = minimal_pe(pkcs7)
    assert authenticode.pkcs7_certificates(authenticode.pe_signature(program)) == [root]
    assert authenticode.find_certificate(program, hashlib.sha256(root).hexdigest()) == root
    with pytest.raises(EditionError, match='no certificate'):
        authenticode.find_certificate(program, '00' * 32)


def test_an_unsigned_or_foreign_file_is_refused():
    with pytest.raises(EditionError, match='not signed'):
        authenticode.pe_signature(minimal_pe(None))
    with pytest.raises(EditionError, match='MZ'):
        authenticode.pe_signature(b'\x7fELF' + bytes(100))
