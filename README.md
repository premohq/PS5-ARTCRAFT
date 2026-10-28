# PS5-ARTCRAFT

The Craft App Suite (PhotoCraft, VectorCraft, FilmCraft, LightCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft,
WordCraft, SoundCraft, DeckCraft, CADCraft, GridCraft) on a jailbroken PS5, on a closed desktop of its own with a file
manager, USB keyboard and mouse, a themed wallpaper, and ArtCraft Launcher starting by itself and updating itself and
the apps as it does on a PC. Built on a fork of [Mihawk OS](https://github.com/premohq/PS5_MihawkOS), which runs
Windows programs on the PS5 through Wine and Proton's stack.

> Status: work in progress, nothing here has run on a console yet. What has been checked, and how, is listed under
> [What is proven](#what-is-proven).

## How it fits together

| Piece | Where | What it does |
|---|---|---|
| The title | `mihawk/patches/` on the fork at `mihawk/mihawk.lock.json` | Boots straight into the ArtCraft desktop on a cold start (a session that ends shows the library, so a failing one never loops); its Start and taskbar keep only File Explorer and Settings; no MihawkBrowser shortcut; the Windows user is ArtCraft |
| The desktop | `artcraft_ps5/stage.py` | A prefix of its own (`artcraft`): `C:\ArtCraft\Launcher` (ArtCraft Launcher, portable), `C:\ArtCraft\Apps\<app>` (each app, installed exactly as the launcher installs a portable ZIP, so the launcher adopts and updates them), the wallpaper, and the library entry that starts it |
| The session start | `session/artcraft-session.c` | Run by the desktop once it is up: installs the code-signing root and policy the launcher's self-update needs, applies the wallpaper and Start pins once, keeps a desktop shortcut per installed app, sets `WGPU_BACKEND=vulkan`, starts the launcher |
| The pins | `edition/suite.lock.json` | Every release the edition installs, by version, URL, size and SHA-256 |

## On the PC

You need an x86_64 Linux machine (or WSL2) with Python 3.10+, `numpy` and `Pillow`, MinGW-w64
(`gcc-mingw-w64-x86-64`) and what the Mihawk fork's README asks for to build the title and runtime.

```sh
# 1. The fork, at its pin, with the edition's patches
git clone https://github.com/premohq/PS5_MihawkOS ../PS5_MihawkOS
git -C ../PS5_MihawkOS checkout -b artcraft b91f6eeef116d824c4307129547dd35adbf42cbe
git -C ../PS5_MihawkOS am "$PWD"/mihawk/patches/*.patch
#    then build and install the title and runtime as its README says (tools/fetch-all.sh,
#    tools/build-production.sh, tools/console-setup.py)

# 2. The session helper
make -C session

# 3. The suite, staged and sent to the console (PS5_HOST / FTP_PORT as in ../PS5_Vulkan/.env)
python3 - <<'EOF'
from pathlib import Path
from artcraft_ps5 import edition, releases, artwork, stage
e = edition.load(need_lock=True)
for pin in e.pins.values():
    releases.download(pin, Path('.deps/downloads'))
wall = Path('.deps/artcraft-wallpaper.bmp')
artwork.save_bmp(artwork.wallpaper([a.rgb for a in e.apps], theme=e.wallpaper_theme, seed=e.wallpaper_seed), wall)
stage.stage(e, Path('.deps/downloads'), Path('dist/artcraft'), Path('session/artcraft-session.exe'), wall)
EOF
python3 -c "from pathlib import Path; from artcraft_ps5 import deploy; deploy.deploy(Path('dist/artcraft'), deploy.console_settings(env_file=Path('../PS5_Vulkan/.env')))"
```

A command-line front end (`python3 -m artcraft_ps5 ...`) is next.

## What is proven

- The suite's releases: all 13 apps and the launcher ship `<app>-<version>-windows-x64-portable.zip` with a
  `SHA256SUMS.txt`; each ZIP holds `<app>.exe` and `<app>-cli.exe` in a version-named folder. All of them are eframe
  0.36 / wgpu 30 apps that honour `WGPU_BACKEND`.
- The session helper, under Wine 9.0 and under GE-Proton 11-7's Wine 11.0 (the archive the fork pins, checksum
  matched): imports the registry (the root certificate's blob lands where crypt32 reads it), writes shortcuts only for
  installed programs and leaves them alone the second time, starts the launcher with `WGPU_BACKEND=vulkan` in its own
  folder.
- The launcher's self-update signature check (`WinVerifyTrust`, as `verifysign` calls it): Wine 9.0 and Wine 11.0 both
  answer *trusted* for the launcher even on a fresh prefix. The signer chain is not trusted there (status 0x21:
  untrusted root, expired end certificate, since Wine reads no RFC 3161 timestamp), but `SoftpubAuthenticode` returns
  S_FALSE without an error and `WinVerifyTrust` reports success. An unsigned or tampered file is still refused. The
  edition also installs the Microsoft Identity Verification Root 2020 (taken from the launcher's own signature, pinned
  by SHA-256) and the `WTPF_IGNOREEXPIRATION` policy, so the check keeps passing if Wine starts enforcing the chain.
- The fork patches: the title code compiles in the host-reference configuration; the shell changes compile with MinGW
  in a mock; the profile move passes the fork's own host test, extended for MihawkOS v3 prefixes, under ASan and UBSan.
  None has run on a console.

## Licences

The patches modify GPL-3.0-or-later code from Mihawk OS (Copyright (C) 2026 Mihawk and the authors credited in its
NOTICE.md). The Craft apps and ArtCraft Launcher are MIT or Apache-2.0, by the ArtCraft team; this repository
downloads their official releases and does not redistribute them. The ArtCraft name and marks belong to their owners.
