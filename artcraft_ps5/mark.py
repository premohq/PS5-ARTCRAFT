"""The edition's mark, one geometry drawn four ways in a Mihawk OS fork, as the fork draws its own mark:

  themes/windows11/start.svg   the mark (the shell's reference; tests/test_taskbar_logo.py renders it with librsvg)
  ps5/tools/icon0.svg          the PS5 tile: the mark on a dark square (icon0.png has no alpha)
  ps5/sce_sys/icon0.png        that SVG rendered at 512 x 512, 8-bit RGB (tests/test_title_icon.py compares them)
  src/pw_taskbar_logo.h        the Start button's mark in C at any size, without libm (Explorer has none)

The mark is a painter's colour wheel, original to this project: one annular sector per Craft app in its brand colour
(edition/suite.json, ordered by hue, the first centred at the top), separated by a small angular gap, around a white
hub with a grey rim. In a 100-unit box centred on 50,50. No ArtCraft logo or mark is used.
"""

from __future__ import annotations

import colorsys
import math
import shutil
import subprocess
from pathlib import Path

CENTRE = 50.0
OUTER, INNER = 47.0, 27.0      # the ring
HUB, RIM = 13.0, 2.0           # the hub's radius and its rim's width (an SVG stroke, centred on the hub's edge)
GAP = 3.0                      # degrees between sectors
HUB_FILL, HUB_RIM = 'FFFFFF', 'C9D3DD'
TILE = '141218'


def ordered(colours: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    return sorted(colours, key=lambda c: colorsys.rgb_to_hsv(*(v / 255 for v in c))[0])


def sectors(colours: list[tuple[int, int, int]]) -> list[tuple[tuple[int, int, int], float, float]]:
    """(colour, start, end) in degrees, clockwise on screen (y down) from the x axis."""
    step = 360.0 / len(colours)
    return [(colour, -90.0 - step / 2 + k * step + GAP / 2, -90.0 + step / 2 + k * step - GAP / 2)
            for k, colour in enumerate(ordered(colours))]


def _point(radius: float, degrees: float) -> str:
    t = math.radians(degrees)
    return f'{CENTRE + radius * math.cos(t):.4f},{CENTRE + radius * math.sin(t):.4f}'


def shapes(colours: list[tuple[int, int, int]]) -> list[str]:
    """The mark's SVG elements, one per line, in drawing order."""
    out = []
    for (r, g, b), start, end in sectors(colours):
        out.append(f'<path d="M{_point(OUTER, start)} A{OUTER:g},{OUTER:g} 0 0 1 {_point(OUTER, end)} '
                   f'L{_point(INNER, end)} A{INNER:g},{INNER:g} 0 0 0 {_point(INNER, start)} Z" '
                   f'fill="#{r:02X}{g:02X}{b:02X}"/>')
    out.append(f'<circle cx="{CENTRE:g}" cy="{CENTRE:g}" r="{HUB:g}" fill="#{HUB_FILL}" stroke="#{HUB_RIM}" '
               f'stroke-width="{RIM:g}"/>')
    return out


def start_svg(colours) -> str:
    body = '\n  '.join(shapes(colours))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- SPDX-License-Identifier: LGPL-2.1-or-later
     ArtCraft mark: original artwork drawn for this edition by PS5-ARTCRAFT's artcraft_ps5/mark.py, a painter's colour
     wheel with one sector per Craft app in its colour around a white hub. It is not derived from any ArtCraft, Microsoft
     or Sony asset. src/pw_taskbar_logo.h draws the same shapes in C. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100" role="img">
  <title>ArtCraft</title>
  {body}
</svg>
'''


def icon_svg(colours) -> str:
    body = '\n  '.join(shapes(colours))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- SPDX-License-Identifier: LGPL-2.1-or-later
     ArtCraft title icon: the mark of themes/windows11/start.svg (its shapes, unchanged; tests/test_title_icon.py checks
     they stay the same) on a dark tile, because the console's icon0.png is RGB, with no alpha.
     sce_sys/icon0.png is rendered from this: rsvg-convert -w 512 -h 512 icon0.svg, then saved as 8-bit RGB. -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512">
  <rect width="100" height="100" fill="#{TILE}"/>
  {body}
</svg>
'''


def logo_header(colours) -> str:
    table = sectors(colours)
    rows = ',\n'.join(
        f'        {{0x{r:02x}{g:02x}{b:02x}, {math.cos(math.radians(s)):+.9f}, {math.sin(math.radians(s)):+.9f}, '
        f'{math.cos(math.radians(e)):+.9f}, {math.sin(math.radians(e)):+.9f}}}'
        for (r, g, b), s, e in table)
    count = len(table)
    return f'''/* SPDX-License-Identifier: GPL-3.0-or-later
 * The Start button's ArtCraft mark at any size, as themes/windows11/start.svg draws it in its 100-unit box: {count} ring
 * sectors (radius {INNER:g} to {OUTER:g} around 50,50, {GAP:g} degrees apart), one per Craft app in its colour, and a white hub (radius {HUB:g})
 * under a {RIM:g}-unit #{HUB_RIM} rim. Written by PS5-ARTCRAFT's artcraft_ps5/mark.py with the SVG, so the two agree. The
 * taskbar draws it at every DPI, 22 px at 96 (Wine patch 1162). Each shape is antialiased by 16 x 16 samples; a sector
 * is the ring between its two edges, told by the signs of two cross products (no trigonometry: Explorer has no libm).
 *
 * Output: extent x extent premultiplied BGRA words (0xAARRGGBB), as GdiAlphaBlend takes them. tests/test_taskbar_logo.py
 * compares it with librsvg's drawing of start.svg. */
#ifndef PW_TASKBAR_LOGO_H
#define PW_TASKBAR_LOGO_H
#include <stdint.h>

enum {{ PW_TASKBAR_LOGO_SECTORS = {count}, PW_TASKBAR_LOGO_LAYERS = {count} + 2 }};

static inline void pw_taskbar_logo(uint32_t *bgra, int extent)
{{
    /* Each sector's colour, then the unit vectors of its first and its last edge, clockwise on screen. */
    static const struct {{ uint32_t rgb; double ax, ay, bx, by; }} sector[PW_TASKBAR_LOGO_SECTORS] = {{
{rows}
    }};
    static const double outer = {OUTER:g} * {OUTER:g}, inner = {INNER:g} * {INNER:g};
    static const double hub = {HUB:g} * {HUB:g}, rim_in = {HUB - RIM / 2:g} * {HUB - RIM / 2:g}, rim_out = {HUB + RIM / 2:g} * {HUB + RIM / 2:g};
    for (int y = 0; y < extent; ++y)
        for (int x = 0; x < extent; ++x)
        {{
            int covered[PW_TASKBAR_LOGO_LAYERS] = {{0}};
            double out[4] = {{0, 0, 0, 0}};  /* premultiplied B, G, R, A in 0..1 */
            uint32_t word = 0;
            for (int sy = 0; sy < 16; ++sy)
                for (int sx = 0; sx < 16; ++sx)
                {{
                    const double dx = (x + (sx + 0.5) / 16) * 100 / extent - 50, dy = (y + (sy + 0.5) / 16) * 100 / extent - 50;
                    const double r2 = dx * dx + dy * dy;
                    if (r2 >= inner && r2 <= outer)
                        for (int k = 0; k < PW_TASKBAR_LOGO_SECTORS; ++k)
                            if (sector[k].ax * dy - sector[k].ay * dx >= 0 && dx * sector[k].by - dy * sector[k].bx >= 0)
                            {{
                                covered[k]++;
                                break;
                            }}
                    covered[PW_TASKBAR_LOGO_SECTORS] += r2 <= hub;
                    covered[PW_TASKBAR_LOGO_SECTORS + 1] += r2 >= rim_in && r2 <= rim_out;
                }}
            /* Each shape antialiased alone and put over what is beneath, as an SVG renderer composes them. */
            for (int layer = 0; layer < PW_TASKBAR_LOGO_LAYERS; ++layer)
            {{
                const uint32_t colour = layer < PW_TASKBAR_LOGO_SECTORS ? sector[layer].rgb :
                                        layer == PW_TASKBAR_LOGO_SECTORS ? 0x{HUB_FILL.lower()} : 0x{HUB_RIM.lower()};
                const double a = covered[layer] / 256.0;
                for (int k = 0; k < 3; ++k) out[k] = (colour >> (8 * k) & 255) / 255.0 * a + out[k] * (1 - a);
                out[3] = a + out[3] * (1 - a);
            }}
            for (int k = 0; k < 4; ++k) word |= (uint32_t)(out[k] * 255 + 0.5) << (8 * k);
            bgra[y * extent + x] = word;
        }}
}}
#endif
'''


def render_icon(svg: Path, png: Path) -> None:
    """icon0.png from icon0.svg with librsvg, as the fork's tests/test_title_icon.py checks it."""
    if not shutil.which('rsvg-convert'):
        raise RuntimeError('rsvg-convert (librsvg) is needed to render the title icon')
    import io

    from PIL import Image
    data = subprocess.run(['rsvg-convert', '-w', '512', '-h', '512', str(svg)], capture_output=True, check=True).stdout
    Image.open(io.BytesIO(data)).convert('RGB').save(png, format='PNG', optimize=True)


def write(fork: Path, colours: list[tuple[int, int, int]]) -> list[Path]:
    paths = {
        'start': fork / 'themes/windows11/start.svg',
        'icon_svg': fork / 'ps5/tools/icon0.svg',
        'icon_png': fork / 'ps5/sce_sys/icon0.png',
        'header': fork / 'src/pw_taskbar_logo.h',
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f'{path}: not a Mihawk OS fork checkout')
    paths['start'].write_text(start_svg(colours))
    paths['icon_svg'].write_text(icon_svg(colours))
    paths['header'].write_text(logo_header(colours))
    render_icon(paths['icon_svg'], paths['icon_png'])
    return list(paths.values())
