"""`python3 -m artcraft_ps5 <command>`: the edition built, staged and sent to the console from one place.

  show        the edition, its suite and what is pinned (and checks all three)
  lock        the pins; with --refresh, pin every app's newest release instead (--dry-run: only list them);
              with --pin ID=VERSION, pin those at those releases and keep the rest (an older one shows its update)
  fetch       download the pinned releases and verify each one
  wallpaper   draw the desktop wallpaper (BMP for Wine; a .png path gives a preview)
  icon        draw the title's icon (512x512 PNG)
  stage       lay out everything the console gets, at the console's paths
  build       fetch, wallpaper and stage in one go
  deploy      send a staged edition to the console over FTP (only what changed; the launcher and the apps go
              once, as ArtCraft Launcher updates them from then on)
  mihawk      the Mihawk OS fork: prepare it (clone at its pin, apply mihawk/patches), or regenerate patches 0005
              to 0007 after a rebase (rebrand, mark, identity; mihawk/README.md)

Every default path is inside this repository (.deps/ for downloads and artwork, dist/ for the staged edition), so the
commands chain with no arguments: `make -C session`, then `build`, then `deploy`.
"""

from __future__ import annotations

import argparse
import ftplib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path

from . import ROOT, artwork, deploy, edition, releases, stage
from .rebrand import RebrandError

DEPS = ROOT / '.deps'
DOWNLOADS = DEPS / 'downloads'
WALLPAPER = DEPS / stage.WALLPAPER
ICON = DEPS / 'artcraft-icon0.png'
STAGED = ROOT / 'dist' / 'artcraft'
SESSION_EXE = ROOT / 'session' / 'artcraft-session.exe'
FORK = ROOT.parent / 'PS5_MihawkOS'                 # where `mihawk prepare` puts the fork by default
ENV_FILE = ROOT.parent / 'PS5_Vulkan' / '.env'     # where the Mihawk fork's tools keep PS5_HOST and FTP_PORT


def _mib(size: int) -> str:
    return f'{size / 2**20:.1f} MiB'


def _apps(e: edition.Edition, ids: list[str] | None) -> tuple[edition.App, ...]:
    return e.chosen_apps(ids if ids else None)


def _installed_at() -> int | None:
    """SOURCE_DATE_EPOCH, when set, so two stagings of the same pins give the same files."""
    value = os.environ.get('SOURCE_DATE_EPOCH')
    if value is None:
        return None
    if not value.isdigit():
        raise edition.EditionError(f'SOURCE_DATE_EPOCH must be whole seconds, not {value!r}')
    return int(value)


def cmd_show(args) -> int:
    e = edition.load(args.edition)
    print(f'{e.title_name} edition {e.version}: title {e.title_id}, profile {e.profile_id} '
          f'(prefix {e.prefix}), root {e.root}')
    print(f'environment: {" ".join(e.environment) or "-"}')
    chosen = {a.id for a in e.chosen_apps()}
    total, missing = 0, []
    for app in (e.launcher, *e.apps):
        pin = e.pins.get(app.id)
        seeded = app.id == e.launcher.id or app.id in chosen
        if pin is None:
            missing.append(app.id)
            version, size = 'unpinned', ''
        else:
            version, size = pin.version, _mib(pin.size)
            total += pin.size if seeded else 0
        mark = '*' if seeded else ' '
        print(f' {mark} {app.id:18} {version:10} {size:>10}  {app.name}: {app.tagline}')
    print(f'* seeded on the console: {len(chosen)} apps and the launcher, {_mib(total)} to download')
    if missing:
        print(f'not pinned: {", ".join(missing)} (run `python3 -m artcraft_ps5 lock --refresh`)')
        return 1
    return 0


def cmd_lock(args) -> int:
    e = edition.load(args.edition)
    path = args.edition / 'suite.lock.json'
    if args.dry_run and not (args.refresh or args.pin):
        raise edition.EditionError('--dry-run goes with --refresh or --pin: `lock --refresh --dry-run`')
    if args.refresh or args.pin:
        versions = None
        if args.pin:
            pairs = [word.split('=', 1) for word in args.pin]
            if any(len(pair) != 2 or not pair[1] for pair in pairs):
                raise edition.EditionError('--pin takes ID=VERSION, like artcraft-launcher=0.8.0')
            versions = {app_id: version.removeprefix('v') for app_id, version in pairs}
        lock = releases.refresh_lock(e, path, versions=versions, write=not args.dry_run)
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        if not args.dry_run:
            print(f'wrote {shown}')
            return 0
        newer = [app_id for app_id, pin in lock['pins'].items()
                 if app_id not in e.pins or e.pins[app_id].version != pin['version']]
        print(f'dry run: {shown} not written; ' +
              (f'{len(newer)} would change: {", ".join(newer)}' if newer else 'every pin is the newest release'))
        return 0
    if not e.pins:
        raise edition.EditionError(f'{path} is missing: run `python3 -m artcraft_ps5 lock --refresh`')
    for app in (e.launcher, *e.apps):
        pin = e.pins.get(app.id)
        print(f'{app.id:18} ' + (f'{pin.version:10} {_mib(pin.size):>10}  {pin.sha256}' if pin else 'unpinned'))
    missing = [a.id for a in (e.launcher, *e.apps) if a.id not in e.pins]
    if missing:
        print(f'not pinned: {", ".join(missing)}')
        return 1
    return 0


def fetch(e: edition.Edition, ids: list[str] | None, downloads: Path) -> None:
    for app in (e.launcher, *_apps(e, ids)):
        pin = e.pins.get(app.id)
        if pin is None:
            raise edition.EditionError(f'{app.id} has no pin: run `python3 -m artcraft_ps5 lock --refresh`')
        path = releases.download(pin, downloads)
        print(f'{app.id:18} {pin.version:10} {path}')


def cmd_fetch(args) -> int:
    fetch(edition.load(args.edition, need_lock=True), args.apps, args.downloads)
    return 0


def draw_wallpaper(e: edition.Edition, out: Path, width: int, height: int) -> Path:
    image = artwork.wallpaper([a.rgb for a in e.apps], width, height, theme=e.wallpaper_theme, seed=e.wallpaper_seed)
    if out.suffix.lower() == '.png':
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out, format='PNG')
    else:
        artwork.save_bmp(image, out)
    print(f'wallpaper ({e.wallpaper_theme}, {width}x{height}): {out}')
    return out


def cmd_wallpaper(args) -> int:
    draw_wallpaper(edition.load(args.edition), args.out, args.width, args.height)
    return 0


def cmd_icon(args) -> int:
    e = edition.load(args.edition)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    artwork.icon([a.rgb for a in e.apps], args.size, seed=e.wallpaper_seed).save(args.out, format='PNG')
    print(f'icon ({args.size}x{args.size}): {args.out}')
    return 0


def _clear_staged(out: Path) -> None:
    """Empty a folder `stage` made before; refuse any other folder, so a typo never deletes something else."""
    if not out.exists():
        return
    if any(out.iterdir()) and not (out / 'manifest.json').is_file():
        raise edition.EditionError(f'{out} has no manifest.json: not a staged edition, so --clean leaves it alone')
    shutil.rmtree(out)


def stage_edition(e: edition.Edition, args) -> stage.Staged:
    if args.clean:
        _clear_staged(args.out)
    return stage.stage(e, args.downloads, args.out, args.session_exe, args.wallpaper, app_ids=args.apps or None,
                       include_cli=True if args.include_cli else None, installed_at=_installed_at())


def cmd_stage(args) -> int:
    stage_edition(edition.load(args.edition, need_lock=True), args)
    return 0


def cmd_build(args) -> int:
    e = edition.load(args.edition, need_lock=True)
    if not args.session_exe.is_file():
        raise edition.EditionError(f'{args.session_exe} is missing: build it with `make -C session`')
    fetch(e, args.apps, args.downloads)
    if args.redraw or not args.wallpaper.is_file():
        draw_wallpaper(e, args.wallpaper, 1920, 1080)
    stage_edition(e, args)
    return 0


def cmd_deploy(args) -> int:
    if not (args.staged / 'manifest.json').is_file():
        raise edition.EditionError(f'{args.staged} is not a staged edition: run `python3 -m artcraft_ps5 build` first')
    console = None if args.dry_run else deploy.console_settings(args.host, args.port, args.env_file)
    deploy.deploy(args.staged, console, dry_run=args.dry_run, force=args.force)
    return 0


def _git(*words: str, cwd: Path | None = None) -> None:
    subprocess.run(['git', *words], cwd=cwd, check=True)


def _head(fork: Path) -> str:
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=fork, check=True, capture_output=True,
                          text=True).stdout.strip()


def prepare_stamp(lock: dict, patches: list[Path]) -> str:
    """What the artcraft branch is made from: the pin and every patch's bytes."""
    digest = hashlib.sha256(lock['commit'].encode())
    for patch in patches:
        digest.update(hashlib.sha256(patch.read_bytes()).digest())
    return digest.hexdigest()


def cmd_mihawk(args) -> int:
    fork = args.dir.resolve()
    e = edition.load(args.edition)
    lock = json.loads((ROOT / 'mihawk' / 'mihawk.lock.json').read_text())
    if args.action == 'prepare':
        patches = sorted((ROOT / 'mihawk' / 'patches').glob('*.patch'))
        # A fork prepared from this pin and these patches, still at the commit that made, is left as it is: build/build.sh
        # runs this each time, and a build resuming after a failure must find what it built from untouched.
        marker = fork / '.git' / 'artcraft-prepared'
        if marker.is_file() and marker.read_text().split() == [prepare_stamp(lock, patches), _head(fork)]:
            print(f'{fork}: branch artcraft, {len(patches)} patches on {lock["commit"][:7]}, already prepared')
            return 0
        if not fork.exists():
            _git('clone', lock['repo'], str(fork))
        status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=fork, check=True,
                                capture_output=True, text=True).stdout
        if status:
            raise edition.EditionError(f'{fork} has changes of its own; commit or stash them first:\n{status}')
        _git('fetch', 'origin', lock['commit'], cwd=fork)
        # The branch is made again from the pin whenever the pin or a patch changed.
        _git('checkout', '-B', 'artcraft', lock['commit'], cwd=fork)
        _git('am', *map(str, patches), cwd=fork)
        marker.write_text(f'{prepare_stamp(lock, patches)} {_head(fork)}\n')
        print(f'{fork}: branch artcraft, {len(patches)} patches applied on {lock["commit"][:7]}; build it with build/build.sh')
    elif args.action == 'rebrand':
        from . import rebrand
        rebrand.rebrand(fork, e.title_name)
    elif args.action == 'mark':
        from . import mark
        for path in mark.write(fork, [app.rgb for app in e.apps]):
            print(path)
    elif args.action == 'identity':
        from . import identity
        identity.identity(fork, e.title_id, e.data_root, e.title_name, lock.get('lapy_daemon_sha256', {}))
    return 0


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog='python3 -m artcraft_ps5', description=__doc__.split('\n\n')[0],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    top.add_argument('--edition', type=Path, default=edition.EDITION_DIR, metavar='DIR',
                     help='the folder with edition.json, suite.json and suite.lock.json (default: edition/)')
    commands = top.add_subparsers(dest='command', required=True, metavar='command')

    def command(name: str, function, text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=text, description=text)
        sub.set_defaults(run=function)
        return sub

    def apps(sub: argparse.ArgumentParser) -> None:
        sub.add_argument('--apps', nargs='+', metavar='ID',
                         help='only these apps (ids from edition/suite.json; default: the edition\'s seed)')

    def downloads(sub: argparse.ArgumentParser) -> None:
        sub.add_argument('--downloads', type=Path, default=DOWNLOADS, metavar='DIR',
                         help='where releases are kept (default: .deps/downloads)')

    def staging(sub: argparse.ArgumentParser) -> None:
        apps(sub)
        downloads(sub)
        sub.add_argument('--out', type=Path, default=STAGED, metavar='DIR', help='default: dist/artcraft')
        sub.add_argument('--session-exe', type=Path, default=SESSION_EXE, metavar='FILE',
                         help='default: session/artcraft-session.exe (make -C session)')
        sub.add_argument('--wallpaper', type=Path, default=WALLPAPER, metavar='FILE',
                         help=f'default: .deps/{stage.WALLPAPER}')
        sub.add_argument('--include-cli', action='store_true', help='also install each app\'s -cli.exe')
        sub.add_argument('--clean', action='store_true', help='empty --out first (only a folder stage made)')

    command('show', cmd_show, 'the edition, its suite and its pins')
    sub = command('lock', cmd_lock, 'the pinned releases')
    sub.add_argument('--refresh', action='store_true', help='pin the newest release of every app and the launcher')
    sub.add_argument('--dry-run', action='store_true', help='with --refresh or --pin: list the releases; write nothing')
    sub.add_argument('--pin', nargs='+', metavar='ID=VERSION', help='pin these at these releases, keep the rest')
    sub = command('fetch', cmd_fetch, 'download and verify the pinned releases')
    apps(sub)
    downloads(sub)
    sub = command('wallpaper', cmd_wallpaper, 'draw the desktop wallpaper')
    sub.add_argument('--out', type=Path, default=WALLPAPER, metavar='FILE',
                     help=f'default: .deps/{stage.WALLPAPER} (.png for a preview)')
    sub.add_argument('--width', type=int, default=1920)
    sub.add_argument('--height', type=int, default=1080)
    sub = command('icon', cmd_icon, 'draw the title\'s icon')
    sub.add_argument('--out', type=Path, default=ICON, metavar='FILE', help='default: .deps/artcraft-icon0.png')
    sub.add_argument('--size', type=int, default=512)
    staging(command('stage', cmd_stage, 'lay out everything the console gets'))
    sub = command('build', cmd_build, 'fetch, draw the wallpaper (once) and stage')
    staging(sub)
    sub.add_argument('--redraw', action='store_true', help='draw the wallpaper again even if it is there')
    sub = command('deploy', cmd_deploy, 'send a staged edition to the console over FTP')
    sub.add_argument('--staged', type=Path, default=STAGED, metavar='DIR', help='default: dist/artcraft')
    sub.add_argument('--host', help='the console\'s address (default: PS5_HOST, from the environment or --env-file)')
    sub.add_argument('--port', type=int, help='ftpsrv\'s port (default: FTP_PORT, else 2121)')
    sub.add_argument('--env-file', type=Path, default=ENV_FILE, metavar='FILE',
                     help='default: ../PS5_Vulkan/.env, as the Mihawk fork\'s tools read it')
    sub.add_argument('--dry-run', action='store_true', help='list what would be sent; connect to nothing')
    sub.add_argument('--force', action='store_true',
                     help='send every file, the launcher and the apps too, over whatever the console has (a repair)')
    sub = command('mihawk', cmd_mihawk, 'the Mihawk OS fork: prepare it, or regenerate patches 0005 to 0007')
    sub.add_argument('action', choices=('prepare', 'rebrand', 'mark', 'identity'))
    sub.add_argument('--dir', type=Path, default=FORK, metavar='DIR', help='the fork (default: ../PS5_MihawkOS)')
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.run(args)
    except (edition.EditionError, RebrandError) as error:
        print(f'error: {error}', file=sys.stderr)
    except subprocess.CalledProcessError as error:
        print(f'error: {error}', file=sys.stderr)
    except urllib.error.URLError as error:
        print(f'error: download failed: {getattr(error, "reason", error)}', file=sys.stderr)
    except (ftplib.Error, OSError) as error:
        print(f'error: {error}', file=sys.stderr)
    except KeyboardInterrupt:
        print('stopped', file=sys.stderr)
        return 130
    return 1
