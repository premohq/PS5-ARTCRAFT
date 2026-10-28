"""python3 -m artcraft_ps5 COMMAND: build, stage and send the ArtCraft edition.

  lock [--refresh]                 show the pinned releases, or pin the newest of each (edition/suite.lock.json)
  fetch [--apps ID ...]            download the launcher and the apps, each checked against its pin (.deps/downloads)
  wallpaper [--theme dark|light]   draw the desktop's wallpaper (.deps/artcraft-wallpaper.bmp)
  stage [--apps ID ...]            lay out everything for the console (dist/artcraft): needs fetch, and
        [--with-cli]               session/artcraft-session.exe (make -C session); draws the wallpaper if missing
  deploy [--dry-run] [--force]     send dist/artcraft to the console over FTP (PS5_HOST and FTP_PORT from the
                                   environment, ../PS5_Vulkan/.env or --host/--port); close the title first.
                                   The launcher and the apps go once: ArtCraft Launcher updates them from then on
  mihawk prepare [--dir DIR]       clone the Mihawk OS fork at its pin into DIR (../PS5_MihawkOS) and apply
                                   mihawk/patches with git am on a branch named artcraft
  mihawk rebrand|mark [--dir DIR]  regenerate patch 0005 or 0006's changes in DIR (after a rebase; mihawk/README.md)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import ROOT
from .edition import EditionError, load

DOWNLOADS = ROOT / '.deps' / 'downloads'
WALLPAPER = ROOT / '.deps' / 'artcraft-wallpaper.bmp'
STAGED = ROOT / 'dist' / 'artcraft'
SESSION_EXE = ROOT / 'session' / 'artcraft-session.exe'
FORK = ROOT.parent / 'PS5_MihawkOS'


def command_lock(args) -> None:
    from . import releases
    edition = load()
    if args.refresh:
        releases.refresh_lock(edition, ROOT / 'edition' / 'suite.lock.json')
        return
    if not edition.pins:
        raise EditionError('no lock yet: run `python3 -m artcraft_ps5 lock --refresh`')
    for pin in edition.pins.values():
        print(f'{pin.id:18} {pin.version:10} {pin.size / 2**20:7.1f} MiB  {pin.sha256[:16]}  {pin.asset}')


def command_fetch(args) -> None:
    from . import releases
    edition = load(need_lock=True)
    ids = [edition.launcher.id] + [app.id for app in edition.chosen_apps(args.apps)]
    for app_id in ids:
        if app_id not in edition.pins:
            raise EditionError(f'{app_id} has no pin: run `lock --refresh`')
        releases.download(edition.pins[app_id], DOWNLOADS)
    print(f'{len(ids)} files in {DOWNLOADS}, each matching its pin')


def draw_wallpaper(theme: str | None = None, out: Path = WALLPAPER) -> Path:
    from . import artwork
    edition = load()
    image = artwork.wallpaper([app.rgb for app in edition.apps], theme=theme or edition.wallpaper_theme,
                              seed=edition.wallpaper_seed)
    artwork.save_bmp(image, out)
    return out


def command_wallpaper(args) -> None:
    print(draw_wallpaper(args.theme, Path(args.out)))


def command_stage(args) -> None:
    import shutil

    from . import stage
    edition = load(need_lock=True)
    if not SESSION_EXE.is_file():
        raise EditionError(f'{SESSION_EXE} is missing: build it with `make -C session` (needs gcc-mingw-w64-x86-64)')
    if not WALLPAPER.is_file():
        print('drawing the wallpaper (about half a minute)')
        draw_wallpaper()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    stage.stage(edition, DOWNLOADS, out, SESSION_EXE, WALLPAPER, app_ids=args.apps,
                include_cli=True if args.with_cli else None)


def command_deploy(args) -> None:
    from . import deploy
    staged = Path(args.staged)
    if not (staged / 'manifest.json').is_file():
        raise EditionError(f'{staged} has no manifest.json: run `stage` first')
    console = None if args.dry_run else deploy.console_settings(args.host, args.port, Path(args.env_file))
    deploy.deploy(staged, console, dry_run=args.dry_run, force=args.force)


def _git(*words: str, cwd: Path | None = None) -> None:
    subprocess.run(['git', *words], cwd=cwd, check=True)


def command_mihawk(args) -> None:
    fork = Path(args.dir).resolve()
    edition = load()
    if args.action == 'prepare':
        lock = json.loads((ROOT / 'mihawk' / 'mihawk.lock.json').read_text())
        if not fork.exists():
            _git('clone', lock['repo'], str(fork))
        _git('fetch', 'origin', lock['commit'], cwd=fork)
        _git('checkout', '-b', 'artcraft', lock['commit'], cwd=fork)
        patches = sorted(str(p) for p in (ROOT / 'mihawk' / 'patches').glob('*.patch'))
        _git('am', *patches, cwd=fork)
        print(f'{fork}: branch artcraft, {len(patches)} patches applied on {lock["commit"][:7]}; build it as its README says')
    elif args.action == 'rebrand':
        from . import rebrand
        rebrand.rebrand(fork, edition.title_name)
    elif args.action == 'mark':
        from . import mark
        for path in mark.write(fork, [app.rgb for app in edition.apps]):
            print(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='python3 -m artcraft_ps5', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    lock = commands.add_parser('lock', help='show or refresh the pinned releases')
    lock.add_argument('--refresh', action='store_true')
    lock.set_defaults(run=command_lock)
    fetch = commands.add_parser('fetch', help='download and verify the pinned releases')
    fetch.add_argument('--apps', nargs='+', metavar='ID')
    fetch.set_defaults(run=command_fetch)
    wallpaper = commands.add_parser('wallpaper', help='draw the desktop wallpaper')
    wallpaper.add_argument('--theme', choices=('dark', 'light'))
    wallpaper.add_argument('--out', default=str(WALLPAPER))
    wallpaper.set_defaults(run=command_wallpaper)
    stage = commands.add_parser('stage', help='lay out everything for the console')
    stage.add_argument('--apps', nargs='+', metavar='ID')
    stage.add_argument('--with-cli', action='store_true', help='also install each app\'s -cli.exe (about 1.1 GB)')
    stage.add_argument('--out', default=str(STAGED))
    stage.set_defaults(run=command_stage)
    deploy = commands.add_parser('deploy', help='send the staged edition to the console over FTP')
    deploy.add_argument('--staged', default=str(STAGED))
    deploy.add_argument('--host')
    deploy.add_argument('--port', type=int)
    deploy.add_argument('--env-file', default=str(ROOT.parent / 'PS5_Vulkan' / '.env'))
    deploy.add_argument('--dry-run', action='store_true', help='list what would be sent; connect to nothing')
    deploy.add_argument('--force', action='store_true',
                        help='send every file, the launcher and the apps too, over whatever the console has (a repair)')
    deploy.set_defaults(run=command_deploy)
    mihawk = commands.add_parser('mihawk', help='the Mihawk OS fork: prepare it, or regenerate patches 0005/0006')
    mihawk.add_argument('action', choices=('prepare', 'rebrand', 'mark'))
    mihawk.add_argument('--dir', default=str(FORK))
    mihawk.set_defaults(run=command_mihawk)
    args = parser.parse_args(argv)
    try:
        args.run(args)
    except (EditionError, OSError, subprocess.CalledProcessError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
