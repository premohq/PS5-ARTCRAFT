"""A Craft app's Windows portable ZIP installed the way ArtCraft Launcher installs one, so the launcher adopts it.

This mirrors storytold/craft-launcher crates/native/src/portable.rs (`install`, `extract`, `flatten_zip_layout`,
`is_root_executable`) at d39702d. What the launcher later relies on, and so what this must produce exactly:

  - the app's folder is named by its id (`recorded_files` refuses any other name);
  - the record's `path` is the folder's root `<stem>.exe` and `files` lists every file installed, as absolute Windows
    paths inside that folder (an update replaces only recorded files; an unrecorded file in its way stops it);
  - `kind` is "PortableZip", so updates stay portable ZIPs (backend.rs `planned_asset`).

A file left out (the `-cli.exe` builds, by default: about 1.1 GB the console never runs) is simply not recorded;
a later update by the launcher brings it back, as it would on a PC.
"""

from __future__ import annotations

import stat
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from .edition import App, EditionError

MAX_FILES = 10_000
MAX_BYTES = 4 * 1024 ** 3


@dataclass(frozen=True)
class Layout:
    """A checked ZIP: each file's member name and its path in the app folder (wrapper folder removed)."""
    files: tuple[tuple[str, PurePosixPath], ...]
    executable: PurePosixPath


def _is_root_executable(relative: PurePosixPath, stems: tuple[str, ...]) -> bool:
    return len(relative.parts) == 1 and any(relative.name.lower() == f'{stem}.exe'.lower() for stem in stems)


def read_layout(archive: zipfile.ZipFile, stems: tuple[str, ...]) -> Layout:
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        raise EditionError('The portable ZIP contains too many files.')
    files, entries, seen, total = [], [], set(), 0
    for info in infos:
        name = info.filename
        relative = PurePosixPath(name.rstrip('/'))
        if (not name or name.startswith('/') or '\\' in name or ':' in name or '\0' in name
                or any(part in ('', '.', '..') for part in name.rstrip('/').split('/'))):
            raise EditionError(f'The portable ZIP contains an unsafe path: {name!r}')
        if info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16):
            raise EditionError(f'The portable ZIP contains a link: {name!r}')
        if str(relative).lower() in seen:
            raise EditionError(f'The portable ZIP contains duplicate paths: {name!r}')
        seen.add(str(relative).lower())
        entries.append(relative)
        if info.is_dir():
            continue
        total += info.file_size
        if total > MAX_BYTES:
            raise EditionError('The portable ZIP is too large.')
        files.append((name, relative))
    if not files:
        raise EditionError('The portable ZIP contains no files.')
    if not any(_is_root_executable(relative, stems) for _, relative in files):
        # One wrapper folder (the release script's `Compress-Archive -Path $Portable`), never arbitrary nesting.
        prefix = files[0][1].parts[0]
        if not all(entry.parts[0] == prefix for entry in entries) or any(len(rel.parts) < 2 for _, rel in files):
            raise EditionError('The portable ZIP has an unsupported directory layout.')
        files = [(name, PurePosixPath(*relative.parts[1:])) for name, relative in files]
    executable = next((rel for _, rel in files if _is_root_executable(rel, stems)), None)
    if executable is None:
        raise EditionError('The portable ZIP does not contain the expected executable at its root.')
    return Layout(tuple(files), executable)


def install(zip_path: Path, app: App, version: str, destination: PureWindowsPath, host_destination: Path, *,
            exclude=lambda relative: False, installed_at: int | None = None) -> dict:
    """Unpack into host_destination (which C:\\... `destination` names on the console); returns the launcher's record."""
    if destination.name != app.id:
        raise EditionError(f'{destination}: the launcher only owns a portable folder named {app.id}')
    stems = (app.id,)
    with zipfile.ZipFile(zip_path) as archive:
        layout = read_layout(archive, stems)
        if exclude(layout.executable):
            raise EditionError(f'{app.id}: the app\'s own executable cannot be left out')
        if host_destination.exists() and any(host_destination.iterdir()):
            raise EditionError(f'{host_destination} is not empty: stage into a fresh folder')
        installed = []
        for name, relative in layout.files:
            if exclude(relative):
                continue
            target = host_destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('xb') as out:
                while block := source.read(1 << 20):
                    out.write(block)
            installed.append(relative)
    return {
        'version': version,
        'kind': 'PortableZip',
        'path': str(destination.joinpath(*layout.executable.parts)),
        'installed_at': int(time.time()) if installed_at is None else installed_at,
        'files': [str(destination.joinpath(*relative.parts)) for relative in installed],
        'needs_root': False,
    }


def unpack_folder(zip_path: Path, stems: tuple[str, ...], host_destination: Path) -> PurePosixPath:
    """Unpack a portable ZIP flat into a folder (the launcher's own copy, which is not a recorded app); its exe."""
    with zipfile.ZipFile(zip_path) as archive:
        layout = read_layout(archive, stems)
        for name, relative in layout.files:
            target = host_destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('wb') as out:
                while block := source.read(1 << 20):
                    out.write(block)
    return layout.executable


def is_cli(app: App):
    """The app's command-line build (`<id>-cli.exe`), which nothing on the console starts."""
    return lambda relative: len(relative.parts) == 1 and relative.name.lower() == f'{app.id}-cli.exe'
