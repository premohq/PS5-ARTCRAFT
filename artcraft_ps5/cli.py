"""`python3 -m artcraft_ps5 <command>`: the edition built, staged and sent to the console from one place.

  show        the edition, its suite and what is pinned (and checks all three)
  lock        the pins; with --refresh, pin every app's newest release instead
  fetch       download the pinned releases and verify each one
  wallpaper   draw the desktop wallpaper (BMP for Wine; a .png path gives a preview)
  icon        draw the title's icon (512x512 PNG)
  stage       lay out everything the console gets, at the console's paths
  build       fetch, wallpaper and stage in one go
  deploy      send a staged edition to the console over FTP (only what changed)

Every default path is inside this repository (.deps/ for downloads and artwork, dist/ for the staged edition), so the
commands chain with no arguments: `make -C session`, then `build`, then `deploy`.
"""

from __future__ import annotations

import argparse
import ftplib
import os
import shutil
import sys
import urllib.error
from pathlib import Path

from . import ROOT, artwork, deploy, edition, releases, stage

DEPS = ROOT / '.deps'
DOWNLOADS = DEPS / 'downloads'
WALLPAPER = DEPS / stage.WALLPAPER
ICON = DEPS / 'artcraft-icon0.png'
STAGED = ROOT / 'dist' / 'artcraft'
SESSION_EXE = ROOT / 'session' / 'artcraft-session.exe'
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
    if args.refresh:
        releases.refresh_lock(e, path)
        print(f'wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}')
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
    sub.add_argument('--force', action='store_true', help='send every file, even ones the console already has')
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.run(args)
    except edition.EditionError as error:
        print(f'error: {error}', file=sys.stderr)
    except urllib.error.URLError as error:
        print(f'error: download failed: {getattr(error, "reason", error)}', file=sys.stderr)
    except (ftplib.Error, OSError) as error:
        print(f'error: {error}', file=sys.stderr)
    except KeyboardInterrupt:
        print('stopped', file=sys.stderr)
        return 130
    return 1
