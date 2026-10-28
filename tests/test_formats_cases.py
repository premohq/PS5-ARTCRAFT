"""The files the edition writes for Windows programs to read: registry files, the launcher's state, signatures."""

import hashlib
import json
import struct
import unittest
from pathlib import PureWindowsPath

from artcraft_ps5 import authenticode, edition, launcher_state, regfile
from tests import fixtures


class RegFile(unittest.TestCase):
    def test_text(self):
        reg = regfile.RegFile()
        reg.string(r'HKEY_CURRENT_USER\Control Panel\Desktop', 'Wallpaper', r'C:\a "b"')
        reg.dword(r'HKEY_CURRENT_USER\Software\X', 'N', 256)
        reg.string(r'HKEY_CURRENT_USER\Control Panel\Desktop', 'Wallpaper', r'C:\ArtCraft\w.bmp')
        self.assertEqual(reg.text(), 'Windows Registry Editor Version 5.00\r\n\r\n'
                                     '[HKEY_CURRENT_USER\\Control Panel\\Desktop]\r\n'
                                     '"Wallpaper"="C:\\\\ArtCraft\\\\w.bmp"\r\n\r\n'
                                     '[HKEY_CURRENT_USER\\Software\\X]\r\n"N"=dword:00000100\r\n\r\n')
        self.assertTrue(reg.encoded().startswith(b'\xff\xfeW\0i\0n\0'))

    def test_multi_string_and_long_binary(self):
        reg = regfile.RegFile()
        reg.multi_string(r'HKEY_CURRENT_USER\S', 'Pins', ['a', 'b'])
        reg.binary(r'HKEY_LOCAL_MACHINE\S', 'Blob', bytes(30))
        text = reg.text()
        self.assertIn('"Pins"=hex(7):61,00,00,00,62,00,00,00,00,00\r\n', text)
        self.assertIn('"Blob"=hex:' + ','.join(['00'] * 25) + ',\\\r\n  ' + ','.join(['00'] * 5) + '\r\n', text)

    def test_only_hkcu_and_hklm(self):
        with self.assertRaises(ValueError):
            regfile.RegFile().dword(r'HKEY_USERS\S', 'N', 1)

    def test_trust_root(self):
        reg = regfile.RegFile()
        thumbprint = regfile.trust_root(reg, fixtures.ROOT_CERT)
        self.assertEqual(thumbprint, hashlib.sha1(fixtures.ROOT_CERT).hexdigest().upper())
        ((name, data),) = reg.keys[f'{regfile.ROOT_STORE}\\{thumbprint}']
        self.assertEqual(name, 'Blob')
        blob = regfile.certificate_blob(fixtures.ROOT_CERT)
        self.assertEqual(struct.unpack_from('<III', blob), (32, 1, len(fixtures.ROOT_CERT)))
        self.assertEqual(data.replace(',\\\r\n  ', ','), 'hex:' + ','.join(f'{b:02x}' for b in blob))


class LauncherState(unittest.TestCase):
    def test_ron_string(self):
        self.assertEqual(launcher_state.ron_string('a"b\\c\nd\x01'), '"a\\"b\\\\c\\nd\\u{1}"')

    def test_app_ron(self):
        settings = {'auto_update': True, 'check_every': 'Hour', 'notify': False, 'preferred_kinds': ['PortableZip'],
                    'ignored': 1}
        ron = launcher_state.settings_ron(settings, PureWindowsPath(r'C:\ArtCraft\Apps'))
        self.assertEqual(ron, '(install_locations:(root:Some("C:\\\\ArtCraft\\\\Apps"),per_app:{}),auto_update:true,'
                              'notify:false,check_every:Hour,preferred_kinds:[PortableZip])')
        text = launcher_state.app_ron(settings, PureWindowsPath(r'C:\ArtCraft\Apps'))
        self.assertTrue(text.startswith('{\n    "settings": "(install_locations:(root:Some(\\"C:\\\\\\\\ArtCraft'))
        self.assertTrue(text.endswith('",\n}\n'))

    def test_installed_json_is_sorted(self):
        data = json.loads(launcher_state.installed_json({'b': {'version': '1'}, 'a': {'version': '2'}}))
        self.assertEqual(list(data['apps']), ['a', 'b'])


class Authenticode(unittest.TestCase):
    def test_certificates_out_of_a_signed_program(self):
        program = fixtures.signed_pe(fixtures.pkcs7(fixtures.CHAIN))
        self.assertEqual(authenticode.pkcs7_certificates(authenticode.pe_signature(program)), fixtures.CHAIN)
        found = authenticode.find_certificate(program, hashlib.sha256(fixtures.ROOT_CERT).hexdigest())
        self.assertEqual(found, fixtures.ROOT_CERT)

    def test_long_chains(self):
        chain = [fixtures.certificate('x' * 300 + str(i)) for i in range(3)]
        program = fixtures.signed_pe(fixtures.pkcs7(chain))
        self.assertEqual(authenticode.pkcs7_certificates(authenticode.pe_signature(program)), chain)

    def test_refusals(self):
        with self.assertRaisesRegex(edition.EditionError, 'not signed'):
            authenticode.pe_signature(fixtures.signed_pe(None))
        with self.assertRaisesRegex(edition.EditionError, 'MZ'):
            authenticode.pe_signature(b'ELF')
        program = fixtures.signed_pe(fixtures.pkcs7(fixtures.CHAIN[:2]))
        with self.assertRaisesRegex(edition.EditionError, 'signing chain'):
            authenticode.find_certificate(program, hashlib.sha256(fixtures.ROOT_CERT).hexdigest())
        with self.assertRaisesRegex(edition.EditionError, 'SignedData'):
            authenticode.pkcs7_certificates(fixtures.der(0x30, fixtures.der(0x06, b'\x2a')))


if __name__ == '__main__':
    unittest.main()
