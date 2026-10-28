#!/usr/bin/env python3
"""Build PS5-ArtCraft's site (GitHub Pages) into a folder: site/index.html filled in from the edition, with the art.

    python3 site/build.py [OUT]        default OUT: _site

The app cards and the dock come from edition/suite.json and the versions from edition/suite.lock.json, so the site
always shows what the edition pins. The pictures are the repository's own (assets/, docs/screenshots/).
"""

from __future__ import annotations

import html
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artcraft_ps5 import ROOT, edition  # noqa: E402

SITE = ROOT / 'site'
REPO = 'https://github.com/premohq/PS5-ARTCRAFT'


def two_tone(name: str) -> str:
    """"PhotoCraft" as the launcher writes it: the first part in ink, "Craft" in the app's colour."""
    base = name.removesuffix('Craft')
    return html.escape(base) + ('<b>Craft</b>' if base != name else '')


def card(app: edition.App, pin: edition.Pin | None) -> str:
    version = f'v{pin.version}' if pin else 'unpinned'
    return f'''
        <article class="card" style="--c: {app.color}">
          <div class="card-head"><span class="version">{html.escape(version)}</span><a href="https://github.com/{app.repo}">GitHub ↗</a></div>
          <div class="card-body">
            <img src="icons/{app.id}.png" alt="" width="60" height="60" loading="lazy">
            <div><div class="name">{two_tone(app.name)}</div><p>{html.escape(app.tagline)}</p></div>
          </div>
        </article>'''


def dock(app: edition.App) -> str:
    return (f'<a href="#apps" title="{html.escape(app.name)}: {html.escape(app.tagline)}">'
            f'<img src="icons/{app.id}.png" alt="{html.escape(app.name)}" width="68" height="68"></a>')


def build(out: Path) -> Path:
    e = edition.load(need_lock=True)
    page = (SITE / 'index.html').read_text()
    page = page.replace('<!-- cards -->', ''.join(card(app, e.pins.get(app.id)) for app in e.apps))
    page = page.replace('<!-- dock -->', '\n        '.join(dock(app) for app in e.apps))
    page = page.replace('{{count}}', str(len(e.apps))).replace('{{others}}', _number(len(e.apps) - 3))
    page = page.replace('{{repo}}', REPO)
    if '{{' in page:
        raise SystemExit(f'site/index.html has a placeholder build.py does not fill: {page[page.index("{{"):][:40]}')
    if out.exists():
        shutil.rmtree(out)
    (out / 'icons').mkdir(parents=True)
    (out / 'index.html').write_text(page)
    (out / '.nojekyll').write_text('')
    shutil.copyfile(SITE / 'style.css', out / 'style.css')
    for app in e.apps:
        shutil.copyfile(ROOT / 'assets' / 'app-icons' / f'{app.id}.png', out / 'icons' / f'{app.id}.png')
    for name in ('icon.png', 'social-preview.png'):
        shutil.copyfile(ROOT / 'assets' / name, out / name)
    shutil.copytree(ROOT / 'docs' / 'screenshots', out / 'screenshots')
    return out


def _number(n: int) -> str:
    words = 'zero one two three four five six seven eight nine ten eleven twelve'.split()
    return words[n] if n < len(words) else str(n)


if __name__ == '__main__':
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '_site')
    print(f'site built in {target}')
