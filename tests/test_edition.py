"""The edition, the suite and the lock as checked in, and what load() refuses."""

import json
import shutil
from pathlib import Path

import pytest

from artcraft_ps5 import edition as edition_module
from artcraft_ps5.edition import EditionError

ROOT = Path(__file__).resolve().parents[1]


def test_the_checked_in_edition_loads_with_every_app_pinned():
    edition = edition_module.load(need_lock=True)
    assert edition.title_name == 'ArtCraft' and edition.prefix == 'artcraft' and len(edition.apps) == 13
    assert set(edition.pins) == {edition.launcher.id} | {app.id for app in edition.apps}
    for pin in edition.pins.values():
        assert pin.asset == f'{pin.id}-{pin.version}-windows-{edition.arch}-portable.zip'
        assert pin.url == f'https://github.com/{next(a.repo for a in (edition.launcher, *edition.apps) if a.id == pin.id)}' \
                          f'/releases/download/{pin.tag}/{pin.asset}'
    assert str(edition.launcher_exe) == r'C:\ArtCraft\Launcher\artcraft-launcher.exe'


def variant(tmp_path, change) -> Path:
    folder = tmp_path / 'edition'
    shutil.copytree(ROOT / 'edition', folder)
    config = json.loads((folder / 'edition.json').read_text())
    change(config)
    (folder / 'edition.json').write_text(json.dumps(config))
    return folder


@pytest.mark.parametrize('change, message', [
    (lambda c: c.update(root=r'C:\Art Craft'), 'without spaces'),
    (lambda c: c.update(root=r'D:\ArtCraft'), 'C:'),
    (lambda c: c.update(environment=['MIHAWK_DESKTOP=0']), 'reserved'),
    (lambda c: c.update(environment=['not a word']), 'NAME=VALUE'),
    (lambda c: c['profile'].update(prefix='mihawk'), 'prefix of its own'),
    (lambda c: c['seed'].update(apps=['nocraft']), 'no app'),
    (lambda c: c['launcher_settings'].update(preferred_kinds=['Dmg']), 'preferred_kinds'),
    (lambda c: c['title'].update(id='artcraft'), 'title id'),
])
def test_what_the_tools_cannot_use_is_refused(tmp_path, change, message):
    with pytest.raises(EditionError, match=message):
        edition_module.load(variant(tmp_path, change))


def test_a_pin_must_be_https_and_a_sha256(tmp_path):
    folder = variant(tmp_path, lambda c: None)
    lock = json.loads((folder / 'suite.lock.json').read_text())
    lock['pins']['photocraft']['url'] = 'http://example.invalid/x.zip'
    (folder / 'suite.lock.json').write_text(json.dumps(lock))
    with pytest.raises(EditionError, match='https'):
        edition_module.load(folder)
