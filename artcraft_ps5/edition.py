"""The edition (edition/edition.json), the suite it installs (edition/suite.json) and the pinned releases
(edition/suite.lock.json), read once and checked, so every other module works from typed values."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import ROOT

EDITION_DIR = ROOT / 'edition'
ID = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
PREFIX_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')       # src/pw_wine_launch.h: prefix folder IDs
ENV_WORD = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=.*$')
# Names the title keeps for itself: not applied when a program opens from the desktop (Mihawk OS README).
RESERVED_ENV = ('PROTON_', 'MIHAWK_', 'WINE_PS5_NTSYNC')
CHECK_EVERY = ('Hour', 'FourHours', 'Day', 'Never')    # craft-launcher crates/ui-egui/src/settings.rs
PACKAGE_KINDS = ('Msi', 'PortableZip')                 # the Windows ones (crates/core/src/platform.rs)
# Mihawk OS's own title and data folder: the edition lives beside it and never takes either.
MIHAWK_TITLE_ID, MIHAWK_DATA_ROOT = 'PPSA99170', '/data/ps5proton'


class EditionError(ValueError):
    """edition.json, suite.json or suite.lock.json says something the tools cannot use."""


@dataclass(frozen=True)
class App:
    id: str
    name: str
    tagline: str
    repo: str
    color: str

    @property
    def rgb(self) -> tuple[int, int, int]:
        return tuple(int(self.color[i:i + 2], 16) for i in (1, 3, 5))


@dataclass(frozen=True)
class Pin:
    """One release asset, pinned: what `fetch` downloads and `stage` unpacks."""
    id: str
    version: str
    tag: str
    asset: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Edition:
    version: str
    title_id: str
    title_name: str
    data_root: PurePosixPath           # the title's runtime, prefixes, library and logs on the console
    profile_id: str
    profile_name: str
    profile_detail: str
    prefix: str
    root: PureWindowsPath
    seed_apps: tuple[str, ...]
    include_cli: bool
    arch: str
    environment: tuple[str, ...]
    launcher_settings: dict
    code_signing_roots: tuple[dict, ...]
    ignore_signature_expiry: bool
    wallpaper_theme: str
    wallpaper_seed: int
    launcher: App
    apps: tuple[App, ...]
    pins: dict[str, Pin] = field(default_factory=dict)

    # Where things live in the prefix, as Windows sees them (C: is <prefix>/drive_c).
    @property
    def launcher_dir(self) -> PureWindowsPath:
        return self.root / 'Launcher'

    @property
    def launcher_exe(self) -> PureWindowsPath:
        return self.launcher_dir / f'{self.launcher.id}.exe'

    @property
    def apps_dir(self) -> PureWindowsPath:
        return self.root / 'Apps'

    @property
    def system_dir(self) -> PureWindowsPath:
        return self.root / 'System'

    @property
    def theme_dir(self) -> PureWindowsPath:
        return self.root / 'Theme'

    def app_exe(self, app: App) -> PureWindowsPath:
        return self.apps_dir / app.id / f'{app.id}.exe'

    def app(self, app_id: str) -> App:
        for app in self.apps:
            if app.id == app_id:
                return app
        raise EditionError(f'no app {app_id!r} in edition/suite.json')

    def chosen_apps(self, ids: list[str] | None = None) -> tuple[App, ...]:
        """The apps to seed: the ones named, else the edition's own choice."""
        wanted = ids if ids is not None else (None if self.seed_apps == ('all',) else list(self.seed_apps))
        return self.apps if wanted is None else tuple(self.app(i) for i in wanted)


def windows_host_path(prefix_dir: Path, path: PureWindowsPath) -> Path:
    """The host file a C:\\ path names inside a prefix folder (C: is drive_c)."""
    if path.drive.upper() != 'C:':
        raise EditionError(f'{path} is not on C:')
    return prefix_dir.joinpath('drive_c', *path.parts[1:])


def _need(table: dict, key: str, kind, where: str):
    value = table.get(key)
    if not isinstance(value, kind):
        raise EditionError(f'{where}: {key} must be a {getattr(kind, "__name__", kind)}')
    return value


def _app(entry: dict, where: str) -> App:
    app = App(**{k: _need(entry, k, str, where) for k in ('id', 'name', 'tagline', 'repo', 'color')})
    if not ID.match(app.id):
        raise EditionError(f'{where}: id {app.id!r} is not a lowercase asset stem')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', app.color):
        raise EditionError(f'{where}: color {app.color!r} is not #rrggbb')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', app.repo):
        raise EditionError(f'{where}: repo {app.repo!r} is not owner/name')
    return app


def _pin(app_id: str, entry: dict) -> Pin:
    where = f'suite.lock.json {app_id}'
    pin = Pin(id=app_id, size=_need(entry, 'size', int, where),
              **{k: _need(entry, k, str, where) for k in ('version', 'tag', 'asset', 'url', 'sha256')})
    if not re.fullmatch(r'[0-9a-f]{64}', pin.sha256):
        raise EditionError(f'{where}: sha256 is not 64 lowercase hex digits')
    if not pin.url.startswith('https://'):
        raise EditionError(f'{where}: url must be https')
    return pin


def load(directory: Path = EDITION_DIR, *, need_lock: bool = False) -> Edition:
    edition = json.loads((directory / 'edition.json').read_text())
    suite = json.loads((directory / 'suite.json').read_text())
    if edition.get('schema') != 1:
        raise EditionError('edition.json: schema must be 1')
    title, profile, seed = (_need(edition, k, dict, 'edition.json') for k in ('title', 'profile', 'seed'))
    trust, wallpaper = _need(edition, 'trust', dict, 'edition.json'), _need(edition, 'wallpaper', dict, 'edition.json')
    launcher = _app(_need(suite, 'launcher', dict, 'suite.json'), 'suite.json launcher')
    apps = tuple(_app(entry, f'suite.json apps[{i}]') for i, entry in enumerate(_need(suite, 'apps', list, 'suite.json')))
    if len({a.id for a in apps}) != len(apps) or launcher.id in {a.id for a in apps}:
        raise EditionError('suite.json: app ids must be unique')
    root = PureWindowsPath(_need(edition, 'root', str, 'edition.json'))
    if root.drive.upper() != 'C:' or not root.is_absolute() or ' ' in str(root) or not str(root).isascii():
        # launch.args splits words on spaces, and the title writes shortcut targets as 7-bit ASCII (src/pw_shell_link.h)
        raise EditionError('edition.json: root must be an absolute C:\\ path, ASCII, without spaces')
    seed_apps = seed.get('apps', 'all')
    seed_apps = ('all',) if seed_apps == 'all' else tuple(_need(seed, 'apps', list, 'edition.json seed'))
    environment = tuple(_need(edition, 'environment', list, 'edition.json'))
    for word in environment:
        if not isinstance(word, str) or not ENV_WORD.match(word):
            raise EditionError(f'edition.json: environment word {word!r} is not NAME=VALUE')
        if word.startswith(RESERVED_ENV):
            raise EditionError(f'edition.json: {word.split("=")[0]} is reserved for the title')
    settings = _need(edition, 'launcher_settings', dict, 'edition.json')
    if settings.get('check_every', 'Hour') not in CHECK_EVERY:
        raise EditionError(f'edition.json: check_every must be one of {", ".join(CHECK_EVERY)}')
    if any(kind not in PACKAGE_KINDS for kind in settings.get('preferred_kinds', [])):
        raise EditionError(f'edition.json: preferred_kinds may name only {", ".join(PACKAGE_KINDS)}')
    roots = tuple(_need(trust, 'code_signing_roots', list, 'edition.json trust'))
    for entry in roots:
        if not re.fullmatch(r'[0-9A-F]{64}', entry.get('sha256', '')) or not re.fullmatch(r'[0-9A-F]{40}', entry.get('sha1', '')):
            raise EditionError('edition.json: a code signing root needs uppercase hex sha1 and sha256')
    result = Edition(
        version=_need(edition, 'version', str, 'edition.json'),
        title_id=_need(title, 'id', str, 'edition.json title'),
        title_name=_need(title, 'name', str, 'edition.json title'),
        data_root=PurePosixPath(_need(title, 'data_root', str, 'edition.json title')),
        profile_id=_need(profile, 'id', str, 'edition.json profile'),
        profile_name=_need(profile, 'name', str, 'edition.json profile'),
        profile_detail=_need(profile, 'detail', str, 'edition.json profile'),
        prefix=_need(profile, 'prefix', str, 'edition.json profile'),
        root=root,
        seed_apps=seed_apps,
        include_cli=bool(seed.get('include_cli', False)),
        arch=seed.get('arch', 'x64'),
        environment=environment,
        launcher_settings=settings,
        code_signing_roots=roots,
        ignore_signature_expiry=bool(trust.get('ignore_signature_expiry', False)),
        wallpaper_theme=wallpaper.get('theme', 'dark'),
        wallpaper_seed=int(wallpaper.get('seed', 0)),
        launcher=launcher,
        apps=apps,
    )
    if not re.fullmatch(r'PPSA[0-9]{5}', result.title_id):
        raise EditionError('edition.json: title id must look like PPSA99278')
    if not re.fullmatch(r'/data/[a-z0-9][a-z0-9_-]{0,31}', str(result.data_root)):
        raise EditionError('edition.json: title data_root must be a folder directly under /data, like /data/artcraft')
    if result.title_id == MIHAWK_TITLE_ID or str(result.data_root) == MIHAWK_DATA_ROOT:
        raise EditionError(f'edition.json: {MIHAWK_TITLE_ID} and {MIHAWK_DATA_ROOT} are Mihawk OS\'s; the edition needs its own')
    if not ID.match(result.profile_id) or not PREFIX_ID.match(result.prefix):
        raise EditionError('edition.json: profile id and prefix must be folder IDs')
    if result.prefix == 'mihawk':
        raise EditionError('edition.json: the edition needs a prefix of its own, not Mihawk OS\'s')
    if result.arch not in ('x64', 'x86'):
        raise EditionError('edition.json: seed arch must be x64 or x86 (the PS5 runs x86-64 and, under WoW64, x86)')
    if result.wallpaper_theme not in ('dark', 'light'):
        raise EditionError('edition.json: wallpaper theme must be dark or light')
    for app_id in (() if seed_apps == ('all',) else seed_apps):
        result.app(app_id)
    lock_file = directory / 'suite.lock.json'
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        pins = {key: _pin(key, value) for key, value in _need(lock, 'pins', dict, 'suite.lock.json').items()}
        unknown = set(pins) - {launcher.id} - {a.id for a in apps}
        if unknown:
            raise EditionError(f'suite.lock.json: pins for apps not in the suite: {", ".join(sorted(unknown))}')
        result.pins.update(pins)
    elif need_lock:
        raise EditionError('edition/suite.lock.json is missing: run `python3 -m artcraft_ps5 lock --refresh`')
    return result
