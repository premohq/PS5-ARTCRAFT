"""Give a Mihawk OS fork's title an identity of its own, so it installs beside Mihawk OS and shares nothing with it.

Mihawk OS is title PPSA99170 and keeps everything under /data/ps5proton: its Wine runtime, prefixes, library, logs,
setup record, update staging, shared sections, the payload child, even the root daemon's log. A second title with
that id replaces it. A second title with that data folder shares its runtime, whose Windows user, Start menu and paths
this edition changes, and its library and records. So every place the fork names either one gets the edition's own
values (edition.json title id and data_root: PPSA99278 and /data/artcraft for ArtCraft). That covers the title, the
runtime, the root daemon's log, and the PC tools that install and test them, with their tests. param.json also gets
a matching conceptId and contentId.

Mihawk OS's documents (*.md) and the records of its console runs (evidence/, docs/history/) stay as they are: they
describe Mihawk OS.

The title updates itself from PROTON_UPDATE_URL, checked with the key in platform/update/release-key.txt. Both are
empty at the fork's pin. If a later Mihawk OS filled them in, ArtCraft would offer Mihawk OS's releases as its own
updates, so this stops without writing anything.

Every rule must match exactly as often as it says. Afterwards only those documents may still name PPSA99170 or
/data/ps5proton.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

from .edition import MIHAWK_DATA_ROOT, MIHAWK_TITLE_ID
from .rebrand import RebrandError, usb_folder

OLD_FOLDER = PurePosixPath(MIHAWK_DATA_ROOT).name
# /data/ps5proton in every spelling the fork uses: a POSIX path, and Z:\data\ps5proton from Windows with its
# backslashes escaped zero to three times over (C strings, Python strings, registry text inside C strings).
OLD_PATH = re.compile(rf'(?<![\w.-])data(/|\\{{1,4}}){OLD_FOLDER}(?![\w-])')
SOURCES = ('.c', '.cpp', '.h', '.hpp', '.py', '.sh', '.json', '.patch', '.txt', '.cmake')
KEPT = ('evidence/', 'docs/history/')
UPDATE_URL = 'set(PROTON_UPDATE_URL "" CACHE STRING'
RELEASE_KEY = 'platform/update/release-key.txt'


def content_id(title_id: str, brand: str) -> str:
    """param.json's contentId: Mihawk OS's publisher part (UP9000), the title id, and a 16-character label."""
    label = usb_folder(brand).upper()[:16].ljust(16, '0')
    return f'UP9000-{title_id}_00-{label}'


def targeted(title_id: str, brand: str) -> list[tuple[str, str, str, int]]:
    """(file, old, new, count): the edits that are not a plain swap, applied first."""
    return [
        ('ps5/sce_sys/param.json', f'"conceptId": "{MIHAWK_TITLE_ID[4:]}"', f'"conceptId": "{title_id[4:]}"', 1),
        ('ps5/sce_sys/param.json', f'"contentId": "UP9000-{MIHAWK_TITLE_ID}_00-PS5PROTON0000000"',
         f'"contentId": "{content_id(title_id, brand)}"', 1),
        # The publication check's own title ids: the edition's joins Mihawk's, which its documents still name.
        ('tools/publication-check.py', f"PPSA(?!{MIHAWK_TITLE_ID[4:]}|", f"PPSA(?!{title_id[4:]}|{MIHAWK_TITLE_ID[4:]}|", 1),
    ]


def tracked(fork: Path) -> list[str]:
    """The fork's own files, never a build's output: what git tracks, minus Mihawk OS's documents and records."""
    names = subprocess.run(['git', 'ls-files', '-z'], cwd=fork, check=True, capture_output=True).stdout.decode().split('\0')
    return sorted(name for name in names if name.endswith(SOURCES) and not name.startswith(KEPT))


def identity(fork: Path, title_id: str, data_root: PurePosixPath, brand: str, *, say=print) -> dict[str, int]:
    if not re.fullmatch(r'PPSA[0-9]{5}', title_id) or title_id == MIHAWK_TITLE_ID:
        raise RebrandError(f'{title_id}: the title needs an id of its own, like PPSA99278')
    if data_root.parent != PurePosixPath('/data') or str(data_root) == MIHAWK_DATA_ROOT:
        raise RebrandError(f'{data_root}: the title needs a folder of its own directly under /data')
    cmake = (fork / 'ps5/CMakeLists.txt').read_text()
    if cmake.count(UPDATE_URL) != 1 or (fork / RELEASE_KEY).exists():
        raise RebrandError(f'the fork now names an update feed or a release key (ps5/CMakeLists.txt PROTON_UPDATE_URL, '
                           f'{RELEASE_KEY}): {brand} would offer Mihawk OS\'s releases as its own. Clear them first.')
    files: dict[str, str] = {}
    changes: dict[str, int] = {}
    def read(name: str) -> str:              # bytes as they are: CRLF files keep their line ends
        return (fork / name).read_bytes().decode()
    for name, old, new, count in targeted(title_id, brand):
        text = files.setdefault(name, read(name))
        if text.count(old) != count:
            raise RebrandError(f'{name}: expected {count} of {old!r}, found {text.count(old)}: the fork moved it')
        files[name] = text.replace(old, new)
        changes[name] = changes.get(name, 0) + count
    for name in tracked(fork):
        try:
            text = files.get(name) or read(name)
        except UnicodeDecodeError:
            data = (fork / name).read_bytes()
            if MIHAWK_TITLE_ID.encode() in data or OLD_PATH.search(data.decode('latin-1')):
                raise RebrandError(f'{name} is not UTF-8 but names Mihawk OS\'s title or folder: change it by hand') from None
            continue
        new, by_id = re.subn(re.escape(MIHAWK_TITLE_ID), title_id, text)
        new, by_path = OLD_PATH.subn(lambda m: f'data{m[1]}{data_root.name}', new)
        if by_id or by_path:
            files[name] = new
            changes[name] = changes.get(name, 0) + by_id + by_path
    left = [name for name, text in files.items() if MIHAWK_TITLE_ID in text or OLD_PATH.search(text)]
    if left:
        raise RebrandError(f'still naming Mihawk OS\'s title or folder: {", ".join(left)}')
    for name, text in files.items():
        (fork / name).write_bytes(text.encode())
    for name, count in sorted(changes.items()):
        say(f'{name}: {count}')
    return changes
