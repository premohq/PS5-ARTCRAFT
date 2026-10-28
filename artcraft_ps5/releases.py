"""The suite's GitHub releases: which Windows portable ZIP each app ships, pinned by SHA-256, and the download.

No GitHub API call (and so no API quota): `releases/latest/download/SHA256SUMS.txt` redirects to the newest release's
checksum list, whose file names carry the version, the same way ArtCraft Launcher finds releases without quota
(its README credits craftcenter for the idea). Every file is checked against the release's own SHA256SUMS.txt.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .edition import App, Edition, EditionError, Pin

USER_AGENT = 'PS5-ARTCRAFT (+https://github.com/premohq/PS5-ARTCRAFT)'
CHUNK = 1 << 20

Opener = Callable[[urllib.request.Request], 'urllib.response.addinfourl']


def parse_sha256sums(text: str) -> dict[str, str]:
    """`<sha256>  <name>` lines (sha256sum's text or binary mode) to {name: sha256}."""
    sums = {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *](.+)', line)
        if not match:
            raise EditionError(f'SHA256SUMS.txt line {number} is not "<sha256>  <file>": {line[:80]!r}')
        sums[match[2]] = match[1].lower()
    return sums


def portable_asset(sums: dict[str, str], stem: str, arch: str = 'x64') -> tuple[str, str]:
    """The release's Windows portable ZIP for `arch`, and the version its name carries."""
    pattern = re.compile(rf'{re.escape(stem)}-(\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)-windows-{re.escape(arch)}-portable\.zip')
    found = [(name, m[1]) for name in sums if (m := pattern.fullmatch(name))]
    if len(found) != 1:
        raise EditionError(f'{stem}: expected one {stem}-<version>-windows-{arch}-portable.zip in SHA256SUMS.txt, '
                           f'found {len(found)}')
    return found[0]


def asset_url(repo: str, tag: str, asset: str) -> str:
    return f'https://github.com/{repo}/releases/download/{tag}/{asset}'


def _open(request: urllib.request.Request, opener: Opener | None):
    request.add_header('User-Agent', USER_AGENT)
    return (opener or urllib.request.urlopen)(request)


def fetch_text(url: str, opener: Opener | None = None) -> str:
    with _open(urllib.request.Request(url), opener) as response:
        return response.read().decode('utf-8')


def remote_size(url: str, opener: Opener | None = None) -> int:
    """The file's size from a one-byte range request (it also proves the URL names a real asset)."""
    with _open(urllib.request.Request(url, headers={'Range': 'bytes=0-0'}), opener) as response:
        content_range = response.headers.get('Content-Range', '')
        if not re.fullmatch(r'bytes 0-0/\d+', content_range):
            raise EditionError(f'{url}: no byte range in the answer ({content_range or response.status})')
        return int(content_range.rsplit('/', 1)[1])


def latest_pin(app: App, arch: str, opener: Opener | None = None) -> Pin:
    sums = parse_sha256sums(fetch_text(f'https://github.com/{app.repo}/releases/latest/download/SHA256SUMS.txt', opener))
    asset, version = portable_asset(sums, app.id, arch)
    tag = f'v{version}'
    url = asset_url(app.repo, tag, asset)
    return Pin(id=app.id, version=version, tag=tag, asset=asset, url=url, sha256=sums[asset], size=remote_size(url, opener))


def refresh_lock(edition: Edition, path: Path, opener: Opener | None = None, *, say=print) -> dict:
    """Pin the newest release of the launcher and every app, and write the lock file."""
    pins = {}
    for app in (edition.launcher, *edition.apps):
        pin = latest_pin(app, edition.arch, opener)
        previous = edition.pins.get(app.id)
        change = '' if not previous else ' (unchanged)' if previous.version == pin.version else f' (was {previous.version})'
        say(f'{app.id:18} {pin.version:10} {pin.size / 2**20:7.1f} MiB  {pin.asset}{change}')
        pins[app.id] = {k: getattr(pin, k) for k in ('version', 'tag', 'asset', 'url', 'sha256', 'size')}
    lock = {
        'comment': 'Written by `python3 -m artcraft_ps5 lock --refresh`; every asset is checked against this sha256.',
        'arch': edition.arch,
        'refreshed': datetime.date.today().isoformat(),
        'pins': pins,
    }
    path.write_text(json.dumps(lock, indent=2) + '\n')
    return lock


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        while block := file.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def download(pin: Pin, directory: Path, opener: Opener | None = None, *, say=print) -> Path:
    """The pinned asset in `directory`, downloaded (resuming a partial one) and verified; a cached file is re-checked."""
    directory.mkdir(parents=True, exist_ok=True)
    target, part = directory / pin.asset, directory / (pin.asset + '.part')
    if target.exists():
        if target.stat().st_size == pin.size and sha256_file(target) == pin.sha256:
            return target
        say(f'{pin.asset}: cached copy does not match its pin; downloading again')
        target.unlink()
    have = part.stat().st_size if part.exists() else 0
    if have > pin.size:
        part.unlink()
        have = 0
    if have < pin.size:
        headers = {'Range': f'bytes={have}-'} if have else {}
        with _open(urllib.request.Request(pin.url, headers=headers), opener) as response:
            if have and response.status != 206:
                have = 0                       # the server ignored the range: start over
            with part.open('ab' if have else 'wb') as out:
                done = have
                while block := response.read(CHUNK):
                    out.write(block)
                    done += len(block)
                    if done > pin.size:
                        break
    actual_size = part.stat().st_size
    actual = sha256_file(part)
    if actual_size != pin.size or actual != pin.sha256:
        part.unlink()
        raise EditionError(f'{pin.asset}: got {actual_size} bytes with sha256 {actual}, '
                           f'the pin says {pin.size} bytes with {pin.sha256}')
    os.replace(part, target)
    say(f'{pin.asset}: {pin.size / 2**20:.1f} MiB, sha256 verified')
    return target
