"""Put the edition's name (edition.json title name) where a Mihawk OS fork shows "MihawkOS" or "Mihawk OS".

Everything the user reads: the title's name and its screens (the loading screen's footer among them), the guided
setup in every language, the desktop's shortcut tips, the logging README, the browser's title, the runtime
wallpaper's corner note, and the USB stick's folder of runtime pieces (artcraft/; the installer still takes a
mihawkos/ one). The credits stay Mihawk's: the About page says the title is a modified version of MihawkOS (GPLv3
section 5a), keeps "Copyright (C) 2026 Mihawk and the authors credited in NOTICE.md" and names both source
repositories; the music is "by Mihawk". Identifiers nobody reads stay, so the fork's tools, formats and existing
prefixes keep working: window classes, HKCU\\Software\\Mihawk keys, the mihawk prefix id, mihawk.exe, pack and release formats,
MihawkBrowser.lnk.

The title's log lines are tagged with its name, so the fork's console tools and their tests now look for
[ArtCraft]; this changes them too.

Every rule must match exactly as often as it says, or nothing is written: a new Mihawk OS release that moved a string
stops here with the file and the text, instead of leaving an old name on screen. After rebasing the fork, drop the
branding commit, run this again on the new base and commit its result (mihawk/README.md).
"""

from __future__ import annotations

import re
from pathlib import Path

WORD = re.compile(r'(?<![\w/.-])(?:MihawkOS|Mihawk OS)(?![\w-])')
C_STRING = re.compile(r'L?"(?:[^"\\\n]|\\.)*"')
CREDITS = ('modified version of', 'github.com', 'music by Mihawk')
# Literals that are not on screen but name something by its old name: a README section a comment points to.
REFERENCES = ('"The Mihawk OS prefix"',)

# Files whose C string literals are screens, notices or files the user reads.
VISIBLE_SOURCES = (
    'src/pw_setup.c', 'src/pw_detailed_logs.c', 'examples/ps5proton/setup_tour.hpp',
    'examples/ps5proton/ps5proton.cpp', 'ps5/src/samples.cpp', 'ps5/src/proton_launch.cpp',
    'native/proton_wine.cpp', 'native/proton_loading.cpp',
)
# Where the USB stick's folder of runtime pieces is named (src/pw_setup.c tells the user its name). The pack format's
# own tags (mihawkos-runtime-pack and the like) are not the folder and stay, as the packs carry them.
USB_FOLDER_FILES = (
    'src/pw_setup.c', 'ps5/src/proton_install.cpp', 'ps5/src/proton_install.h', 'examples/ps5proton/ps5proton.cpp',
    'tools/package-install.py', 'tests/test_package_install.py', 'tools/run-setup-unattended.py',
)
USB_FOLDER = re.compile(r'(?<![\w-])mihawkos(?![\w-])')
OLD_STICK = 'a stick made for MihawkOS'
# Tools and tests that read the title's log, tagged with its name.
LOG_READERS = (
    'tools/run-launcher.py', 'tools/run-console.py', 'tools/run-setup-unattended.py',
    'tests/test_console_setup.py', 'tests/test_run_console_verdicts.py', 'tests/test_console_guard.py',
)


def usb_folder(brand: str) -> str:
    """The USB stick's folder for this brand: its name in lowercase letters and digits (artcraft)."""
    return re.sub(r'[^a-z0-9]', '', brand.lower())


def targeted(brand: str) -> list[tuple[str, str, str, int]]:
    """(file, old, new, count): the edits that are not a plain name swap, applied first."""
    folder = usb_folder(brand)
    a = 'an' if folder[:1] in tuple('aeiou') else 'a'
    return [
        ('ps5/src/proton_install.cpp', 'folders.push_back(mount + "/mihawkos");',
         f'folders.push_back(mount + "/{folder}");\n\t\tfolders.push_back(mount + "/mihawkos");   /* {OLD_STICK} */', 1),
        ('ps5/src/proton_install.cpp', 'or in a mihawkos folder on a USB stick.', f'or in {a} {folder} folder on a USB stick.', 1),
        ('examples/ps5proton/ps5proton.cpp', 'or in a mihawkos folder on a USB stick.',
         f'or in {a} {folder} folder on a USB stick.', 1),
        ('examples/ps5proton/ps5proton.cpp',
         "and the Mihawk desktop unloads while it plays.", 'and the desktop unloads while it plays.', 1),
        ('examples/ps5proton/ps5proton.cpp',
         'PS5_TITLE_NAME ". Copyright (C) 2026 Mihawk and the authors credited in NOTICE.md."',
         'PS5_TITLE_NAME ", a modified version of MihawkOS. Copyright (C) 2026 Mihawk and the authors credited in "\n'
         '\t\t\t\t"NOTICE.md."', 1),
        ('examples/ps5proton/ps5proton.cpp', '"Source: github.com/mihawk-99/PS5_MihawkOS"',
         '"Source: github.com/premohq/PS5_MihawkOS, a fork of github.com/mihawk-99/PS5_MihawkOS"', 1),
        ('examples/ps5proton/ps5proton.cpp', '"MihawkOS\'s own music, made for it: Bubble Garden,',
         '"Original music by Mihawk: Bubble Garden,', 1),
        ('examples/ps5proton/ps5proton.cpp', '(Mihawk OS and entries with a prefix of their own;',
         '(the Windows desktop and entries with a prefix of their own;', 1),
        ('ps5/src/proton_launch.cpp', 'desktop.name = "Mihawk OS";', f'desktop.name = "{brand} Windows desktop";', 1),
        ('ps5/src/proton_launch.cpp', '"edition: %s, profile %s, Mihawk OS desktop %s, browser shortcut %s"',
         '"edition: %s, profile %s, the Windows desktop %s, browser shortcut %s"', 1),
        ('src/pw_browser.c', 'L"%.*s - MihawkBrowser"', f'L"%.*s - {brand} Browser"', 1),
        ('src/pw_browser.c', 'CreateWindowExW(0, L"MihawkBrowser", L"MihawkBrowser",',
         f'CreateWindowExW(0, L"MihawkBrowser", L"{brand} Browser",', 1),
        ('src/pw_browser.c', 'L"MihawkBrowser opens https:// addresses only."',
         f'L"{brand} Browser opens https:// addresses only."', 1),
        ('tools/build-wine-theme.py',
         "note = [f'MihawkOS v{(ROOT / \"VERSION\").read_text().strip()}', 'https://discord.gg/mihawk']",
         f"note = ['{brand}']", 1),
        ('tests/test_pw_detailed_logs.c', '"MihawkOS detailed logs"', f'"{brand} detailed logs"', 1),
        ('tools/run-setup-unattended.py', "'setup: the first Mihawk OS session starts'",
         f"'setup: the first {brand} session starts'", 1),
        ('tools/run-setup-unattended.py', "'the Mihawk OS session did not reach its desktop; stopped here'",
         f"'the {brand} session did not reach its desktop; stopped here'", 1),
        ('ps5/sce_sys/param.json', '"titleName": "MihawkOS"', f'"titleName": "{brand}"', 1),
        # The one name split across two literals (the setup's Italian).
        ('src/pw_setup.c', 'Il desktop di Mihawk "\n        "OS resta in inglese.',
         f'Il desktop di {brand} "\n        "resta in inglese.', 1),
    ]


class RebrandError(ValueError):
    pass


def _strings(text: str, brand: str) -> tuple[str, int]:
    count = 0

    def literal(match: re.Match) -> str:
        nonlocal count
        value = match[0]
        if any(credit in value for credit in CREDITS) or value in REFERENCES:
            return value
        new, n = WORD.subn(brand, value)
        count += n
        return new
    return C_STRING.sub(literal, text), count


def rebrand(fork: Path, brand: str, *, say=print) -> dict[str, int]:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ]{0,30}', brand):
        raise RebrandError(f'{brand!r}: a brand is letters, digits and spaces')
    files: dict[str, str] = {}

    def text(name: str) -> str:
        if name not in files:
            path = fork / name
            if not path.is_file():
                raise RebrandError(f'{name} is not in {fork}')
            files[name] = path.read_text()
        return files[name]

    changes: dict[str, int] = {}
    for name, old, new, count in targeted(brand):
        found = text(name).count(old)
        if found != count:
            raise RebrandError(f'{name}: expected {count} of {old!r}, found {found}: the fork moved it')
        files[name] = files[name].replace(old, new)
        changes[name] = changes.get(name, 0) + count
    for name in VISIBLE_SOURCES:
        files[name], count = _strings(text(name), brand)
        changes[name] = changes.get(name, 0) + count
    for name in LOG_READERS:
        new = text(name).replace('[MihawkOS]', f'[{brand}]').replace(r'\[MihawkOS\]', rf'\[{brand}\]')
        count = text(name).count('[MihawkOS]') + text(name).count(r'\[MihawkOS\]')
        files[name] = re.sub(r'(?<![\w/.-])Mihawk OS(?= session)', brand, new) if name.endswith('unattended.py') else new
        changes[name] = changes.get(name, 0) + count
    folder = usb_folder(brand)
    for name in USB_FOLDER_FILES:
        lines = text(name).split('\n')
        count = 0
        for i, line in enumerate(lines):
            if OLD_STICK not in line:
                lines[i], n = USB_FOLDER.subn(folder, line)
                count += n
        files[name] = '\n'.join(lines)
        changes[name] = changes.get(name, 0) + count
    readme = text('tools/package-install.py')
    files['tools/package-install.py'], count = WORD.subn(brand, readme)
    changes['tools/package-install.py'] = count
    left = {name: [m[0] for m in C_STRING.finditer(files[name]) if WORD.search(m[0]) and m[0] not in REFERENCES and
                   not any(c in m[0] for c in CREDITS)] for name in VISIBLE_SOURCES}
    left = {name: found for name, found in left.items() if found}
    if left:
        raise RebrandError(f'names left on screen: {left}')
    for name, content in files.items():
        (fork / name).write_text(content)
    for name, count in sorted(changes.items()):
        say(f'{name}: {count}')
    return changes

