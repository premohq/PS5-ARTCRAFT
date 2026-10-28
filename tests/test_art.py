"""The edition's pictures: the wallpaper and the mark, and the rebrand's string rules."""

import shutil
import subprocess

import pytest

from artcraft_ps5 import artwork, mark, rebrand
from artcraft_ps5.edition import load

COLOURS = [app.rgb for app in load().apps]


def test_the_wallpaper_is_seeded_and_sized():
    first = artwork.wallpaper(COLOURS, 192, 108, 'dark', seed=7)
    assert first.size == (192, 108) and first.mode == 'RGB'
    assert first.tobytes() == artwork.wallpaper(COLOURS, 192, 108, 'dark', seed=7).tobytes()
    assert first.tobytes() != artwork.wallpaper(COLOURS, 192, 108, 'light', seed=7).tobytes()


def test_the_mark_has_a_sector_per_app_starting_at_the_top():
    sectors = mark.sectors(COLOURS)
    assert len(sectors) == 13
    first_start, first_end = sectors[0][1], sectors[0][2]
    assert abs((first_start + first_end) / 2 - -90) < 1e-9          # centred at the top
    assert abs(sectors[1][1] - first_end - mark.GAP) < 1e-9          # a gap between neighbours
    shapes = mark.shapes(COLOURS)
    assert len(shapes) == 14 and shapes[-1].startswith('<circle')
    assert mark.icon_svg(COLOURS).count('<path') == 13 and 'ArtCraft' in mark.start_svg(COLOURS)


@pytest.mark.skipif(not shutil.which('cc'), reason='no C compiler')
def test_the_c_mark_compiles_and_draws_a_symmetric_shape(tmp_path):
    (tmp_path / 'pw_taskbar_logo.h').write_text(mark.logo_header(COLOURS))
    (tmp_path / 'main.c').write_text('#include <stdio.h>\n#include <stdlib.h>\n#include "pw_taskbar_logo.h"\n'
                                     'int main(void){uint32_t p[22*22];pw_taskbar_logo(p,22);fwrite(p,4,22*22,stdout);return 0;}\n')
    subprocess.run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror', f'-I{tmp_path}', str(tmp_path / 'main.c'),
                    '-o', str(tmp_path / 'logo')], check=True)
    import numpy as np
    words = np.frombuffer(subprocess.run([str(tmp_path / 'logo')], capture_output=True, check=True).stdout, '<u4')
    alpha = (words.reshape(22, 22) >> 24).astype(int)
    assert alpha[0, 0] == 0 and alpha[11, 11] == 255
    assert np.abs(alpha - alpha[:, ::-1]).max() <= 1


def test_rebrand_swaps_names_in_strings_but_keeps_credits_and_identifiers():
    text = ('paint("Welcome to MihawkOS"); say("the first Mihawk OS session"); '
            'x("Source: github.com/mihawk-99/PS5_MihawkOS"); y("a modified version of MihawkOS"); '
            'z(L"MihawkOSX"); w("PS5_MihawkOS"); /* MihawkOS in a comment */ v("mihawkos folder");')
    out, count = rebrand._strings(text, 'ArtCraft')
    assert '"Welcome to ArtCraft"' in out and '"the first ArtCraft session"' in out and count == 2
    for kept in ('github.com/mihawk-99/PS5_MihawkOS', 'a modified version of MihawkOS', 'MihawkOSX', '"PS5_MihawkOS"',
                 '/* MihawkOS in a comment */', 'mihawkos folder'):
        assert kept in out


def test_rebrand_stops_on_a_fork_that_moved_a_string(tmp_path):
    (tmp_path / 'ps5/src').mkdir(parents=True)
    (tmp_path / 'ps5/src/proton_install.cpp').write_text('nothing to see')
    with pytest.raises(rebrand.RebrandError, match='proton_install.cpp: expected 1'):
        rebrand.rebrand(tmp_path, 'ArtCraft', say=lambda *a: None)
    assert (tmp_path / 'ps5/src/proton_install.cpp').read_text() == 'nothing to see'   # nothing written
    assert rebrand.usb_folder('ArtCraft') == 'artcraft' and rebrand.usb_folder('Art Craft 2') == 'artcraft2'
