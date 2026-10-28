"""Send a staged edition (artcraft_ps5/stage.py) to the console over FTP: the ftpsrv payload on port 2121.

The console's address comes from the same place the Mihawk fork's tools read it (../PS5_Vulkan/.env: PS5_HOST,
FTP_PORT), or from the environment or the command line; it is never printed in full (the fork's rule 5).

What it does, as the fork's tools/deploy-folder.py does:
  - asks ftpsrv for SELF off first (with it on, a signed file reads back decrypted, so nothing would compare);
  - writes each file as .<name>.upload beside its place and renames it into place, so a cut transfer never leaves
    half a program where the old one was;
  - keeps a manifest of what it sent (sha256 per file) in the prefix folder, and next time sends only what changed.

Close the ArtCraft title on the console first: a running desktop holds its programs open.
"""

from __future__ import annotations

import ftplib
import io
import json
import os
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from .edition import EditionError

REMOTE_MANIFEST = '.artcraft-deploy.json'


@dataclass(frozen=True)
class Console:
    host: str
    port: int = 2121
    user: str = 'anonymous'
    password: str = ''

    @property
    def masked(self) -> str:
        """The address with its middle hidden (rule 5 of the fork: nothing private in logs)."""
        parts = self.host.split('.')
        shown = f'{parts[0]}.*.*.{parts[-1]}' if len(parts) == 4 else self.host[:2] + '***'
        return f'{shown}:{self.port}'


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*', line)
        if match and not line.lstrip().startswith('#'):
            values[match[1]] = match[2].strip('"\'')
    return values


def console_settings(host: str | None = None, port: int | None = None, env_file: Path | None = None,
                     environ=os.environ) -> Console:
    values = dict(read_env_file(env_file)) if env_file and env_file.is_file() else {}
    values.update({k: v for k, v in environ.items() if k in ('PS5_HOST', 'FTP_PORT', 'FTP_USER', 'FTP_PASSWORD')})
    host = host or values.get('PS5_HOST')
    if not host:
        raise EditionError('no console address: set PS5_HOST (or ../PS5_Vulkan/.env, or pass --host)')
    return Console(host=host, port=int(port or values.get('FTP_PORT') or 2121),
                   user=values.get('FTP_USER', 'anonymous'), password=values.get('FTP_PASSWORD', ''))


def plan(staged: Path, remote: dict[str, str], force: bool = False) -> tuple[list[dict], list[dict]]:
    """(files to send, files already current) from the staged manifest and the console's last one."""
    manifest = json.loads((staged / 'manifest.json').read_text())
    send, keep = [], []
    for entry in manifest['files']:
        if '/drive_c/windows/' in entry['path'].lower():
            raise EditionError(f'{entry["path"]}: never written (wineboot makes C:\\windows)')
        (keep if not force and remote.get(entry['path']) == entry['sha256'] else send).append(entry)
    return send, keep


class Uploader:
    def __init__(self, ftp: ftplib.FTP):
        self.ftp = ftp
        self.made: set[str] = set()

    def self_off(self) -> None:
        """ftpsrv's SELF toggles decryption of signed files on download; it must read `disabled`."""
        for _ in range(3):
            try:
                reply = self.ftp.sendcmd('SELF')
            except ftplib.error_perm:
                return                       # not ftpsrv (a test server): nothing to turn off
            if 'disabled' in reply.lower():
                return
        raise EditionError(f'ftpsrv kept SELF on: {reply}')

    def makedirs(self, directory: str) -> None:
        parts, path = directory.strip('/').split('/'), ''
        for part in parts:
            path += '/' + part
            if path in self.made:
                continue
            try:
                self.ftp.mkd(path)
            except ftplib.error_perm:
                pass                         # it is there already (or the next store says why not)
            self.made.add(path)

    def put(self, local: Path, remote: str) -> None:
        directory, name = posixpath.split(remote)
        self.makedirs(directory)
        temporary = f'{directory}/.{name}.upload'
        with local.open('rb') as file:
            self.ftp.storbinary(f'STOR {temporary}', file, blocksize=1 << 16)
        try:
            self.ftp.delete(remote)
        except ftplib.error_perm:
            pass
        self.ftp.rename(temporary, remote)

    def read_json(self, remote: str) -> dict:
        buffer = io.BytesIO()
        try:
            self.ftp.retrbinary(f'RETR {remote}', buffer.write)
        except ftplib.error_perm:
            return {}
        try:
            return json.loads(buffer.getvalue())
        except ValueError:
            return {}

    def write_json(self, remote: str, value: dict) -> None:
        directory, name = posixpath.split(remote)
        self.makedirs(directory)
        self.ftp.storbinary(f'STOR {remote}', io.BytesIO(json.dumps(value, indent=1).encode()))


def deploy(staged: Path, console: Console | None, *, dry_run: bool = False, force: bool = False, say=print,
           connect=ftplib.FTP) -> list[dict]:
    manifest = json.loads((staged / 'manifest.json').read_text())
    remote_manifest = posixpath.join(manifest['prefix'], REMOTE_MANIFEST)
    if dry_run:
        send, _ = plan(staged, {}, force=True)
        for entry in send:
            say(f'would send {entry["path"]} ({entry["size"]} bytes)')
        say(f'{len(send)} files, {sum(e["size"] for e in send) / 2**20:.1f} MiB (dry run: nothing sent)')
        return send
    if console is None:
        raise EditionError('no console to send to')
    ftp = connect()
    ftp.connect(console.host, console.port, timeout=60)
    ftp.login(console.user, console.password)
    say(f'connected to {console.masked}')
    try:
        uploader = Uploader(ftp)
        uploader.self_off()
        sent = uploader.read_json(remote_manifest).get('files', {})
        send, keep = plan(staged, sent, force=force)
        say(f'{len(send)} files to send, {len(keep)} already current')
        for number, entry in enumerate(send, 1):
            uploader.put(staged / entry['path'].lstrip('/'), entry['path'])
            sent[entry['path']] = entry['sha256']
            if number % 50 == 0 or number == len(send):
                say(f'  {number}/{len(send)} {entry["path"]}')
                uploader.write_json(remote_manifest, {'edition': manifest['edition'], 'files': sent})
        uploader.write_json(remote_manifest, {'edition': manifest['edition'], 'files': sent})
    finally:
        try:
            ftp.quit()
        except (ftplib.Error, OSError):
            ftp.close()
    say(f'done: {len(send)} sent, {sum(e["size"] for e in send) / 2**20:.1f} MiB')
    return send
