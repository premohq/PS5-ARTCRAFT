"""The two files ArtCraft Launcher reads from its portable data folder, written before it ever runs.

Portable mode (`portable.txt` beside the exe) keeps everything in `ArtCraftLauncherData` (crates/native/src/paths.rs):

  ArtCraftLauncherData/data/installed.json   the records of what it installed (manifest.rs, serde_json)
  ArtCraftLauncherData/data/app.ron          its settings, in eframe's storage file (apps/artcraft-launcher/src/
                                             settings_file.rs): a RON map of keys to RON-encoded strings, the
                                             settings under "settings"

`Settings` is `#[serde(default)]`, so the settings string names only the fields the edition sets; the launcher fills
in the rest and rewrites the whole file on its first save.
"""

from __future__ import annotations

import json
from pathlib import PureWindowsPath

DATA = ('ArtCraftLauncherData', 'data')
SETTINGS_KEY = 'settings'   # apps/artcraft-launcher/src/main.rs SETTINGS_KEY


def installed_json(records: dict[str, dict]) -> str:
    return json.dumps({'apps': dict(sorted(records.items()))}, indent=2) + '\n'


def ron_string(text: str) -> str:
    """A RON (Rust-style) string literal."""
    out = []
    for char in text:
        if char in '\\"':
            out.append('\\' + char)
        elif char == '\n':
            out.append('\\n')
        elif char == '\t':
            out.append('\\t')
        elif ord(char) < 0x20:
            out.append(f'\\u{{{ord(char):x}}}')
        else:
            out.append(char)
    return '"' + ''.join(out) + '"'


def settings_ron(settings: dict, apps_folder: PureWindowsPath) -> str:
    """The launcher's `Settings` struct in RON: the edition's choices plus the folder new portable installs go in."""
    fields = [f'install_locations:(root:Some({ron_string(str(apps_folder))}),per_app:{{}})']
    for key in ('auto_update', 'notify', 'close_to_tray', 'prereleases'):
        if key in settings:
            fields.append(f'{key}:{"true" if settings[key] else "false"}')
    if 'check_every' in settings:
        fields.append(f'check_every:{settings["check_every"]}')
    if 'preferred_kinds' in settings:
        fields.append(f'preferred_kinds:[{",".join(settings["preferred_kinds"])}]')
    return '(' + ','.join(fields) + ')'


def app_ron(settings: dict, apps_folder: PureWindowsPath) -> str:
    """eframe's storage file: {"settings": "<Settings in RON>"}."""
    return '{\n    ' + ron_string(SETTINGS_KEY) + ': ' + ron_string(settings_ron(settings, apps_folder)) + ',\n}\n'
