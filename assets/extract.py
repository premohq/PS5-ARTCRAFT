#!/usr/bin/env python3
"""Take the README art's source material out of the pinned releases (run `python3 -m artcraft_ps5 fetch` first).

  assets/app-icons/<id>.png   each Craft app's own icon, the 256 px image in its <id>.exe exactly as shipped
                              (MIT OR Apache-2.0, see assets/app-icons/ATTRIBUTION.md)
  .deps/fonts/<family>.ttf    the typefaces ArtCraft Launcher draws with (Archivo, Inter, Geist Mono; SIL OFL 1.1),
                              found in its program; kept out of the repository, used only by assets/render.cjs

The launcher's own icon is the ArtCraft "A" mark, a trademark that is not open source: it is never taken.
"""

from __future__ import annotations

import io
import re
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artcraft_ps5 import ROOT, edition, portable  # noqa: E402

ICONS = ROOT / 'assets' / 'app-icons'
FONTS = ROOT / '.deps' / 'fonts'
FAMILIES = ('Archivo', 'Inter', 'Geist Mono')
RT_ICON, RT_GROUP_ICON = 3, 14
PNG = b'\x89PNG\r\n\x1a\n'


def resources(program: bytes, kind: int) -> dict[int, bytes]:
    """{id: data} for one resource type of a PE file (first language of each)."""
    pe = struct.unpack_from('<I', program, 0x3c)[0]
    count, optional_size = struct.unpack_from('<H', program, pe + 6)[0], struct.unpack_from('<H', program, pe + 20)[0]
    optional = pe + 24
    directories = optional + {0x10b: 96, 0x20b: 112}[struct.unpack_from('<H', program, optional)[0]]
    resource_rva = struct.unpack_from('<I', program, directories + 2 * 8)[0]
    sections = [struct.unpack_from('<8sIIII', program, optional + optional_size + 40 * i)[1:] for i in range(count)]

    def offset(rva: int) -> int:
        for virtual_size, address, raw_size, pointer in sections:
            if address <= rva < address + max(virtual_size, raw_size):
                return pointer + rva - address
        raise ValueError(f'RVA {rva:#x} is in no section')

    base = offset(resource_rva)

    def entries(directory: int):
        named, ids = struct.unpack_from('<HH', program, base + directory + 12)
        for i in range(named + ids):
            yield struct.unpack_from('<II', program, base + directory + 16 + 8 * i)

    found = {}
    for type_id, types in entries(0):
        if type_id != kind:
            continue
        for name, languages in entries(types & 0x7fffffff):
            _, leaf = next(entries(languages & 0x7fffffff))
            rva, size = struct.unpack_from('<II', program, base + leaf)
            found[name] = program[offset(rva):offset(rva) + size]
    return found


def largest_icon(program: bytes) -> bytes:
    """The largest image of the program's first icon group, as PNG (as stored when it is one)."""
    groups, images = resources(program, RT_GROUP_ICON), resources(program, RT_ICON)
    group = groups[min(groups)]
    count = struct.unpack_from('<H', group, 4)[0]
    members = [struct.unpack_from('<BBBBHHIH', group, 6 + 14 * i) for i in range(count)]
    best = max(members, key=lambda m: (m[0] or 256, m[5]))
    data = images[best[7]]
    if data.startswith(PNG):
        return data
    from PIL import Image                  # a bitmap entry: wrap it in a one-image .ico for Pillow to read
    header = struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', *best[:6], len(data), 22)
    out = io.BytesIO()
    Image.open(io.BytesIO(header + data)).save(out, format='PNG')
    return out.getvalue()


def fonts(program: bytes) -> dict[str, bytes]:
    """{family: TrueType file} of the fonts a program carries inside it."""
    found = {}
    for match in re.finditer(rb'\x00\x01\x00\x00(?=\x00[\x05-\x20])', program):
        start = match.start()
        tables = {}
        for i in range(struct.unpack_from('>H', program, start + 4)[0]):
            tag, _, at, length = struct.unpack_from('>4sIII', program, start + 12 + 16 * i)
            tables[tag] = (at, length)
        if b'name' not in tables or not all(re.fullmatch(rb'[ -~]{4}', tag) for tag in tables):
            continue
        end = max(at + length for at, length in tables.values())
        font = program[start:start + end]
        family = _family(font, *tables[b'name'])
        if family and len(font) == end:
            found.setdefault(family, font)
    return found


def _family(font: bytes, at: int, length: int) -> str | None:
    """The typographic family (name ID 16, else 1) from a font's Windows-platform names."""
    if at + length > len(font):
        return None
    count, strings = struct.unpack_from('>HH', font, at + 2)
    names = {}
    for i in range(count):
        platform, _, _, name_id, size, offset = struct.unpack_from('>HHHHHH', font, at + 6 + 12 * i)
        if platform == 3 and name_id in (1, 16):
            names.setdefault(name_id, font[at + strings + offset:at + strings + offset + size].decode('utf-16-be'))
    return names.get(16) or names.get(1)


def program_in(zip_path: Path, stem: str) -> bytes:
    with zipfile.ZipFile(zip_path) as archive:
        layout = portable.read_layout(archive, (stem,))
        member = next(name for name, relative in layout.files if relative == layout.executable)
        return archive.read(member)


def attribution(e: edition.Edition) -> str:
    rows = [f'| `{app.id}.png` | {app.name} | ArtCraft Team and the {app.name} contributors | `{app.id}.exe` in '
            f'[`{e.pins[app.id].asset}`]({e.pins[app.id].url}) ([`{app.repo}`](https://github.com/{app.repo})) | '
            f'MIT OR Apache-2.0 |' for app in e.apps]
    return '\n'.join([
        '# Craft App Suite icons',
        '',
        'Each app\'s own icon: the 256 px image of the icon in its Windows program, taken out unmodified by',
        '`assets/extract.py` from the release `edition/suite.lock.json` pins. Copyright (c) 2026 ArtCraft Team and each',
        'app\'s contributors, under the app\'s license, MIT OR Apache-2.0 (ArtCraft Launcher\'s NOTICE and ATTRIBUTION.md',
        'list the same icons under the same terms). The ArtCraft name, wordmark and "A" mark are trademarks of the',
        'ArtCraft Team and are not used here.',
        '',
        '| File | App | Author | Source | License |',
        '|---|---|---|---|---|',
        *rows,
        '',
    ])


def main() -> int:
    e = edition.load(need_lock=True)
    downloads = ROOT / '.deps' / 'downloads'
    ICONS.mkdir(parents=True, exist_ok=True)
    for app in e.apps:
        icon = largest_icon(program_in(downloads / e.pins[app.id].asset, app.id))
        (ICONS / f'{app.id}.png').write_bytes(icon)
        print(f'{app.id}: {e.pins[app.id].version}, icon {len(icon)} bytes')
    (ICONS / 'ATTRIBUTION.md').write_text(attribution(e))
    FONTS.mkdir(parents=True, exist_ok=True)
    found = fonts(program_in(downloads / e.pins[e.launcher.id].asset, e.launcher.id))
    for family in FAMILIES:
        if family not in found:
            raise SystemExit(f'{family} is not in {e.launcher.id} {e.pins[e.launcher.id].version}')
        (FONTS / f'{family.replace(" ", "")}.ttf').write_bytes(found[family])
        print(f'font: {family}, {len(found[family])} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
