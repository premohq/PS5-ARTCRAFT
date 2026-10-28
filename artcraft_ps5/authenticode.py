"""The certificates inside a Windows program's Authenticode signature, read without running or trusting it.

The launcher's signature (Azure Trusted Signing) carries its whole chain, root included:
Learning Machines Inc <- Microsoft ID Verified CS EOC CA 03 <- Microsoft ID Verified Code Signing PCA 2021 <-
Microsoft Identity Verification Root Certificate Authority 2020. Wine's crypt32 does not ship that root, so the
edition takes it from here and installs it (pinned by SHA-256 in edition.json); nothing Microsoft-made is vendored.
"""

from __future__ import annotations

import hashlib
import struct

from .edition import EditionError

WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002
SIGNED_DATA_OID = bytes.fromhex('2a864886f70d010702')   # 1.2.840.113549.1.7.2


def _tlv(data: bytes, at: int) -> tuple[int, int, int, int]:
    """(tag, value start, value end, element end) of the DER element at `at`."""
    if at + 2 > len(data):
        raise EditionError('truncated DER')
    tag, first = data[at], data[at + 1]
    if tag & 0x1f == 0x1f:
        raise EditionError('multi-byte DER tags are not expected in a signature')
    at += 2
    if first < 0x80:
        length = first
    else:
        count = first & 0x7f
        if count == 0 or count > 4 or at + count > len(data):
            raise EditionError('bad DER length')
        length = int.from_bytes(data[at:at + count], 'big')
        at += count
    if at + length > len(data):
        raise EditionError('DER element runs past its parent')
    return tag, at, at + length, at + length


def _children(data: bytes, start: int, end: int):
    at = start
    while at < end:
        tag, value, value_end, at = _tlv(data, at)
        yield tag, value, value_end


def pkcs7_certificates(der: bytes) -> list[bytes]:
    """The encoded certificates of a PKCS#7 SignedData's `certificates` field."""
    tag, start, end, _ = _tlv(der, 0)
    content = list(_children(der, start, end)) if tag == 0x30 else []
    if len(content) < 2 or content[0][0] != 0x06 or der[content[0][1]:content[0][2]] != SIGNED_DATA_OID:
        raise EditionError('not a PKCS#7 SignedData')
    explicit = content[1]
    signed = list(_children(der, explicit[1], explicit[2]))
    if explicit[0] != 0xa0 or len(signed) != 1 or signed[0][0] != 0x30:
        raise EditionError('PKCS#7 content is not SignedData')
    certificates = []
    for tag, value, value_end in _children(der, signed[0][1], signed[0][2]):
        if tag == 0xa0:                                    # certificates [0] IMPLICIT SET OF Certificate
            at = value
            while at < value_end:
                _, _, _, end_of = _tlv(der, at)
                certificates.append(der[at:end_of])
                at = end_of
    return certificates


def pe_signature(program: bytes) -> bytes:
    """The PKCS#7 blob of a PE file's first Authenticode certificate (the security data directory)."""
    if program[:2] != b'MZ':
        raise EditionError('not a Windows program (no MZ header)')
    pe = struct.unpack_from('<I', program, 0x3c)[0]
    if program[pe:pe + 4] != b'PE\0\0':
        raise EditionError('not a PE file')
    optional = pe + 24
    magic = struct.unpack_from('<H', program, optional)[0]
    directories = optional + {0x10b: 96, 0x20b: 112}.get(magic, -1)
    if directories < optional:
        raise EditionError(f'unknown PE optional header magic {magic:#x}')
    offset, size = struct.unpack_from('<II', program, directories + 4 * 8)
    if not offset or size < 8 or offset + size > len(program):
        raise EditionError('the program is not signed')
    length, _revision, kind = struct.unpack_from('<IHH', program, offset)
    if kind != WIN_CERT_TYPE_PKCS_SIGNED_DATA or length < 8 or length > size:
        raise EditionError(f'unexpected WIN_CERTIFICATE type {kind:#x}')
    return program[offset + 8:offset + length]


def find_certificate(program: bytes, sha256: str) -> bytes:
    """The certificate with this SHA-256 (hex, any case) from the program's signature."""
    for certificate in pkcs7_certificates(pe_signature(program)):
        if hashlib.sha256(certificate).hexdigest().upper() == sha256.upper():
            return certificate
    raise EditionError(f'no certificate with sha256 {sha256} in the program\'s signature: the publisher may have '
                       f'changed its signing chain; pin the new root in edition/edition.json')
