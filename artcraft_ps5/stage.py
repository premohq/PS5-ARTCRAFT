"""Everything the edition puts on the console, laid out under one folder whose paths are the console's own.

  <out>/data/ps5proton/prefixes/<prefix>/drive_c/ArtCraft/   C:\\ArtCraft in the edition's prefix:
      Launcher/   ArtCraft Launcher's portable copy, portable.txt beside its exe, and its data folder seeded with
                  installed.json (the apps below, as its own installs) and app.ron (its settings)
      Apps/<id>/  each app's portable ZIP, unpacked as the launcher unpacks one (artcraft_ps5/portable.py)
      System/     artcraft-session.exe, session.ini, trust.reg and defaults.reg
      Theme/      the wallpaper
  <out>/data/ps5proton/games/<profile>/game.json          the library entry that starts the ArtCraft desktop
  <out>/data/homebrew/<title>/edition.json                 tells the (patched) title to start that entry itself
  <out>/manifest.json                                      every file: its console path, size and sha256

Nothing is written under drive_c/windows: wineboot makes that folder, and one made before it breaks a new prefix
(Mihawk src/pw_wine_launch.h). drive_c/ArtCraft beside it is safe: the title makes the prefix folder, drive_c and
the drive links only where they are missing (native/proton_wine.cpp).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import authenticode, launcher_state, portable, regfile
from .edition import Edition, EditionError, windows_host_path

DATA_ROOT = PurePosixPath('/data/ps5proton')
PUBLIC_DESKTOP = PureWindowsPath(r'C:\users\Public\Desktop')
SESSION_ENTRY = r'C:\windows\system32\mihawk.exe'      # the desktop session's entry (Mihawk src/pw_desktop_session.h)
# The built-in Mihawk OS entry's environment (ps5/src/proton_launch.cpp proton_read_games): a desktop session.
SESSION_ENV = ['PROTON_LAYOUT=launcher', 'WINE_PS5_WINDOW_SURFACES=1', 'MIHAWK_DESKTOP=1']
START_PINS_MAX = 18                                    # wine/ps5/pw_shell_start.c PW_START_PINS
WALLPAPER = 'artcraft-wallpaper.bmp'


@dataclass(frozen=True)
class Staged:
    out: Path
    files: int
    size: int
    apps: tuple[str, ...]


def console_paths(edition: Edition) -> dict[str, PurePosixPath]:
    return {
        'prefix': DATA_ROOT / 'prefixes' / edition.prefix,
        'entry': DATA_ROOT / 'games' / edition.profile_id / 'game.json',
        'edition': PurePosixPath('/data/homebrew') / edition.title_id / 'edition.json',
    }


def game_json(edition: Edition) -> dict:
    return {
        'name': edition.profile_name,
        'detail': edition.profile_detail,
        'executable': SESSION_ENTRY,
        'arguments': str(edition.system_dir / 'artcraft-session.exe'),
        'directory': str(edition.root),
        'prefix': edition.prefix,
        'env': SESSION_ENV,
        'desktop': False,
    }


def title_edition_json(edition: Edition) -> dict:
    """What mihawk/patches teach the title to read from its folder (ps5/src/proton_launch.cpp proton_edition)."""
    return {
        'name': edition.title_name,
        'profile': edition.profile_id,
        'hide_mihawk_desktop': True,
        'browser_shortcut': False,
    }


def link_path(name: str) -> PureWindowsPath:
    return PUBLIC_DESKTOP / f'{name}.lnk'


def shortcuts(edition: Edition) -> list[tuple[str, PureWindowsPath]]:
    """Every program that gets a desktop shortcut once it is installed: the launcher, then the suite."""
    return [(edition.launcher.name, edition.launcher_exe)] + [(app.name, edition.app_exe(app)) for app in edition.apps]


def trust_registry(edition: Edition, roots: list[bytes]) -> regfile.RegFile:
    reg = regfile.RegFile()
    for der in roots:
        regfile.trust_root(reg, der)
    if edition.ignore_signature_expiry:
        reg.dword(regfile.SOFTWARE_PUBLISHING, 'State', regfile.WTPF_DEFAULT | regfile.WTPF_IGNOREEXPIRATION)
    return reg


def defaults_registry(edition: Edition, seeded: list[str]) -> regfile.RegFile:
    reg = regfile.RegFile()
    reg.string(r'HKEY_CURRENT_USER\Control Panel\Desktop', 'Wallpaper', str(edition.theme_dir / WALLPAPER))
    reg.dword(r'HKEY_CURRENT_USER\Software\MihawkOS', 'WallpaperInitialized', 1)
    names = {app.id: app.name for app in edition.apps}
    pins = [r'C:\windows\explorer.exe', str(link_path(edition.launcher.name))]
    pins += [str(link_path(names[app_id])) for app_id in seeded]
    reg.multi_string(r'HKEY_CURRENT_USER\Software\Mihawk\Shell', 'StartPins', pins[:START_PINS_MAX])
    reg.dword(r'HKEY_CURRENT_USER\Software\Mihawk\Shell', 'BrowserPinned', 1)
    return reg


def session_ini(edition: Edition, defaults_id: str) -> str:
    system = edition.system_dir
    lines = [
        '[session]',
        f'launcher={edition.launcher_exe}',
        f'trust={system / "trust.reg"}',
        f'defaults={system / "defaults.reg"}',
        f'defaults_id={defaults_id}',
        f'wallpaper={edition.theme_dir / WALLPAPER}',
        f'desktop={PUBLIC_DESKTOP}',
        f'log={system / "logs" / "session.log"}',
        '',
        '[environment]',
        *edition.environment,
        '',
        '[shortcuts]',
        *(f'{name}={program}' for name, program in shortcuts(edition)),
    ]
    text = '\r\n'.join(lines) + '\r\n'
    if not text.isascii():
        raise EditionError('session.ini must be ASCII (GetPrivateProfileString reads it in the ANSI code page)')
    return text


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, newline='')
    else:
        path.write_bytes(data)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while block := file.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def stage(edition: Edition, downloads: Path, out: Path, session_exe: Path, wallpaper: Path, *,
          app_ids: list[str] | None = None, include_cli: bool | None = None, installed_at: int | None = None,
          say=print) -> Staged:
    if out.exists() and any(out.iterdir()):
        raise EditionError(f'{out} is not empty: stage into a fresh folder (or remove it first)')
    if not session_exe.is_file():
        raise EditionError(f'{session_exe} is missing: build it with `make -C session`')
    if not wallpaper.is_file():
        raise EditionError(f'{wallpaper} is missing: draw it with `python3 -m artcraft_ps5 wallpaper`')
    apps = edition.chosen_apps(app_ids)
    include_cli = edition.include_cli if include_cli is None else include_cli
    paths = console_paths(edition)
    prefix_dir = out / paths['prefix'].relative_to('/')

    def host(path: PureWindowsPath) -> Path:
        return windows_host_path(prefix_dir, path)

    def asset(app_id: str) -> Path:
        pin = edition.pins.get(app_id)
        if pin is None:
            raise EditionError(f'{app_id} has no pin in edition/suite.lock.json')
        file = downloads / pin.asset
        if not file.is_file():
            raise EditionError(f'{file} is missing: run `python3 -m artcraft_ps5 fetch`')
        return file

    # The launcher: a portable copy (portable.txt beside the exe keeps all its state in ArtCraftLauncherData) that
    # updates itself by unzipping its next release over this folder, as on a PC.
    launcher_zip = asset(edition.launcher.id)
    executable = portable.unpack_folder(launcher_zip, (edition.launcher.id,), host(edition.launcher_dir))
    if PureWindowsPath(*executable.parts) != PureWindowsPath(edition.launcher_exe.name):
        raise EditionError(f'the launcher ZIP\'s program is {executable}, not {edition.launcher_exe.name}')
    if not host(edition.launcher_dir / 'portable.txt').is_file():
        raise EditionError('the launcher ZIP has no portable.txt: it would keep its state outside its folder')
    say(f'{edition.launcher.id}: {edition.pins[edition.launcher.id].version} -> {edition.launcher_dir}')

    records = {}
    for app in apps:
        pin = edition.pins[app.id]
        destination = edition.apps_dir / app.id
        records[app.id] = portable.install(asset(app.id), app, pin.version, destination, host(destination),
                                           exclude=(lambda _: False) if include_cli else portable.is_cli(app),
                                           installed_at=installed_at)
        say(f'{app.id}: {pin.version} -> {destination} ({len(records[app.id]["files"])} files)')
    data = edition.launcher_dir.joinpath(*launcher_state.DATA)
    _write(host(data / 'installed.json'), launcher_state.installed_json(records))
    _write(host(data / 'app.ron'), launcher_state.app_ron(edition.launcher_settings, edition.apps_dir))

    # The code-signing root comes out of the launcher's own signature, checked against its pin.
    program = host(edition.launcher_exe).read_bytes()
    roots = [authenticode.find_certificate(program, root['sha256']) for root in edition.code_signing_roots]
    defaults = defaults_registry(edition, [app.id for app in apps])
    defaults_bytes = defaults.encoded()
    defaults_id = f'{edition.version}-{hashlib.sha256(defaults_bytes).hexdigest()[:12]}'
    system = edition.system_dir
    _write(host(system / 'trust.reg'), trust_registry(edition, roots).encoded())
    _write(host(system / 'defaults.reg'), defaults_bytes)
    _write(host(system / 'session.ini'), session_ini(edition, defaults_id))
    host(system).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(session_exe, host(system / 'artcraft-session.exe'))
    host(edition.theme_dir).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(wallpaper, host(edition.theme_dir / WALLPAPER))

    _write(out / paths['entry'].relative_to('/'), json.dumps(game_json(edition), indent=2) + '\n')
    _write(out / paths['edition'].relative_to('/'), json.dumps(title_edition_json(edition), indent=2) + '\n')

    windows_dir = prefix_dir / 'drive_c' / 'windows'
    if windows_dir.exists():
        raise EditionError(f'{windows_dir} must not be staged: wineboot makes it')
    entries = []
    for file in sorted(p for p in out.rglob('*') if p.is_file()):
        entries.append({'path': '/' + file.relative_to(out).as_posix(), 'size': file.stat().st_size,
                        'sha256': _sha256(file)})
    manifest = {'edition': edition.version, 'prefix': str(paths['prefix']), 'apps': [a.id for a in apps],
                'files': entries}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    size = sum(e['size'] for e in entries)
    say(f'staged {len(entries)} files, {size / 2**20:.1f} MiB, in {out}')
    return Staged(out, len(entries), size, tuple(a.id for a in apps))
