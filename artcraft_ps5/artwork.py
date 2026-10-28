"""The edition's own artwork, drawn by code: the desktop wallpaper and the title's PS5 icon.

Original pictures in the Craft App Suite's colours (edition/suite.json), seeded so a run always gives the same pixels,
the way the Mihawk fork draws its Aero Meadow (tools/make-mihawk-wallpaper.py). No ArtCraft name, logo or mark is
drawn: those are the ArtCraft team's trademarks.

Wallpaper, "Studio Ribbons": one brush stroke per app sweeping across a canvas, bristle streaks along each stroke,
canvas grain and a vignette. The strokes keep to the right of the desktop's icon column. Drawn at twice the size and
downsampled, which antialiases every edge.
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

PALETTES = {
    'dark': {'top': (0.055, 0.050, 0.070), 'bottom': (0.020, 0.018, 0.026), 'lift': (0.20, 0.16, 0.30),
             'lift_alpha': 0.22, 'glow': 0.30, 'alpha': 0.92, 'grain': 0.022, 'vignette': 0.55, 'sheen': 0.35},
    'light': {'top': (0.965, 0.955, 0.935), 'bottom': (0.915, 0.900, 0.870), 'lift': (1.0, 0.98, 0.93),
              'lift_alpha': 0.55, 'glow': 0.0, 'alpha': 0.86, 'grain': 0.030, 'vignette': 0.18, 'sheen': 0.22},
}


def _np():
    import numpy
    return numpy


def _smoothstep(np, edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _ordered(colours):
    """The colours by hue, so neighbouring strokes blend."""
    return sorted(colours, key=lambda c: colorsys.rgb_to_hsv(*c)[0])


def wallpaper(colours: list[tuple[int, int, int]], width: int = 1920, height: int = 1080, theme: str = 'dark',
              seed: int = 20261027):
    """A PIL image of the wallpaper."""
    np = _np()
    from PIL import Image
    p = PALETTES[theme]
    rng = np.random.default_rng(seed)
    w, h = width * 2, height * 2
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    aspect = w / h
    top, bottom = np.array(p['top'], np.float32), np.array(p['bottom'], np.float32)
    image = top + (bottom - top) * y[..., None]
    image = np.broadcast_to(image, (h, w, 3)).copy()
    # a soft light from the upper right, where the strokes gather
    d = np.sqrt(((x - 0.78) * aspect) ** 2 + (y - 0.28) ** 2)
    lift = p['lift_alpha'] * np.exp(-(d / 0.75) ** 2)
    image += (np.array(p['lift'], np.float32) - image) * lift[..., None]
    glow = np.zeros((h, w), np.float32)
    strokes = _ordered([tuple(v / 255 for v in c) for c in colours])
    count = len(strokes)
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)
    for i, colour in enumerate(strokes):
        t = (i + 0.5) / count
        # each stroke enters low on the left and rises to the right; together they fan out like a brush's sweep
        base = 0.98 - 0.80 * t
        rise = 0.30 + 0.25 * rng.random()
        amplitude = 0.035 + 0.05 * rng.random()
        frequency = 1.4 + 1.6 * rng.random()
        phase = rng.random() * math.tau
        start = 0.20 + 0.12 * rng.random() + 0.10 * (1 - t)
        end = 0.92 + 0.10 * rng.random()
        centre = base - rise * (xs - 0.5) + amplitude * np.sin(frequency * math.tau * xs + phase) \
            + 0.4 * amplitude * np.sin(2.3 * frequency * math.tau * xs + 1.7 * phase)
        slope = np.gradient(centre, xs) / aspect
        along = np.clip((xs - start) / (end - start), 0.0, 1.0)
        # a brush stroke: it swells from a point, holds, and lifts off with a dry tail
        thickness = (0.010 + 0.022 * rng.random()) * (np.clip(np.sin(math.pi * along ** 0.8), 0.0, 1.0) ** 0.6) \
            * (1 + 0.25 * np.sin(5.0 * math.tau * xs + phase))
        thickness = np.where((xs > start) & (xs < end), thickness, 0.0).astype(np.float32)
        across = (y - centre[None, :]) / np.sqrt(1 + slope[None, :] ** 2)
        u = across / np.maximum(thickness[None, :], 1e-6)            # -1..1 across the stroke
        body = 1.0 - _smoothstep(np, 0.70, 1.0, np.abs(u))
        # bristles: fine streaks across the stroke's width, thinning towards its dry tail
        lanes = sum(rng.random() * np.sin((8 + 40 * rng.random()) * u + rng.random() * math.tau) for _ in range(6))
        dry = _smoothstep(np, 0.55, 1.0, along)[None, :]
        bristle = np.clip(0.80 + 0.12 * lanes, 0.0, 1.0)
        coverage = body * (1.0 - dry * _smoothstep(np, -0.2, 0.6, lanes))
        coverage = np.clip(coverage * p['alpha'], 0.0, 1.0)
        c = np.array(colour, np.float32)
        shade = c * (0.80 + 0.20 * bristle[..., None])
        sheen = p['sheen'] * np.exp(-((u + 0.35) / 0.25) ** 2)       # wet paint catching the light
        shade = shade + (1.0 - shade) * sheen[..., None]
        image += (shade - image) * coverage[..., None]
        if p['glow']:
            glow += coverage * 0.5 + np.exp(-(np.abs(across) / np.maximum(thickness[None, :] * 3.5, 1e-6)) ** 2) * 0.10
            image += c * (p['glow'] * 0.04) * np.exp(-(np.abs(across) / 0.08) ** 2)[..., None] \
                * (thickness[None, :] > 0)[..., None]
    grain = rng.normal(0.0, p['grain'], (h // 2, w // 2)).astype(np.float32)
    grain = np.repeat(np.repeat(grain, 2, axis=0), 2, axis=1)
    image += grain[..., None]
    vignette = np.sqrt(((x - 0.5) * aspect / 1.2) ** 2 + (y - 0.5) ** 2)
    image *= 1.0 - p['vignette'] * _smoothstep(np, 0.45, 1.05, vignette)[..., None]
    pixels = (np.clip(image, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(pixels, 'RGB').resize((width, height), Image.LANCZOS)


def icon(colours: list[tuple[int, int, int]], size: int = 512, seed: int = 20261027):
    """The title's icon: a painter's colour wheel, one brushed arc per app, on a dark tile."""
    np = _np()
    from PIL import Image
    rng = np.random.default_rng(seed)
    s = size * 2
    c = np.linspace(-1.0, 1.0, s, dtype=np.float32)
    x, y = c[None, :], c[:, None]
    r = np.sqrt(x * x + y * y)
    angle = (np.arctan2(y, x) + math.pi / 2) % math.tau
    top, bottom = np.array((0.09, 0.085, 0.11), np.float32), np.array((0.03, 0.028, 0.04), np.float32)
    image = top + (bottom - top) * ((y + 1) / 2)[..., None]
    image = np.broadcast_to(image, (s, s, 3)).copy()
    strokes = _ordered([tuple(v / 255 for v in col) for col in colours])
    span = math.tau / len(strokes)
    for i, colour in enumerate(strokes):
        centre = (i + 0.5) * span
        offset = (angle - centre + math.pi) % math.tau - math.pi
        width = 0.47 * span * (0.85 + 0.15 * rng.random())
        radius = 0.56 + 0.03 * rng.random()
        band = 0.20 + 0.04 * rng.random()
        along = 1.0 - _smoothstep(np, width * 0.93, width, np.abs(offset))
        across = 1.0 - _smoothstep(np, band * 0.95, band, np.abs(r - radius))
        lanes = sum(rng.random() * np.sin((30 + 60 * rng.random()) * (r - radius) + rng.random() * 6) for _ in range(4))
        coverage = np.clip(along * across, 0, 1)[..., None]
        shade = np.array(colour, np.float32) * (0.85 + 0.08 * lanes)[..., None]
        image += (shade - image) * coverage
    hub = 1.0 - _smoothstep(np, 0.160, 0.166, r)
    image += (np.array((0.96, 0.95, 0.93), np.float32) - image) * hub[..., None]
    pixels = (np.clip(image, 0.0, 1.0) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(pixels, 'RGB').resize((size, size), Image.LANCZOS)


def save_bmp(image, path: Path) -> None:
    """24-bit BMP: what Wine's desktop loads as a wallpaper (LoadImage, LR_LOADFROMFILE)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(path, format='BMP')
