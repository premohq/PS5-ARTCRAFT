<p align="center">
  <img src="assets/banner.png" alt="PS5-ArtCraft: the Craft App Suite on PlayStation 5, thirteen apps that update themselves, with USB keyboard and mouse" width="100%">
</p>

<p align="center">
  <a href="https://github.com/premohq/PS5-ARTCRAFT/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/premohq/PS5-ARTCRAFT?include_prereleases&label=release&color=3b8cff"></a>
  <a href="https://ko-fi.com/premohq"><img alt="Ko-fi: support PS5-ARTCRAFT" src="https://img.shields.io/badge/ko--fi-support%20PS5--ARTCRAFT-FF5E5B?logo=kofi&logoColor=white"></a>
  <a href="https://www.paypal.com/paypalme/empthe"><img alt="PayPal: support PS5-ARTCRAFT" src="https://img.shields.io/badge/paypal-support%20PS5--ARTCRAFT-00457C?logo=paypal&logoColor=white"></a>
  <img alt="Status: work in progress" src="https://img.shields.io/badge/status-work%20in%20progress-f07a1e">
  <img alt="Platform: PS5 homebrew" src="https://img.shields.io/badge/platform-PS5%20homebrew-1f5fd6">
  <a href="https://github.com/premohq/PS5_MihawkOS"><img alt="Built on Mihawk OS" src="https://img.shields.io/badge/built%20on-Mihawk%20OS-5cd3ff"></a>
  <a href="#the-suite"><img alt="Suite: 13 Craft apps" src="https://img.shields.io/badge/suite-13%20Craft%20apps-2f7bf5"></a>
  <img alt="Input: USB keyboard and mouse" src="https://img.shields.io/badge/input-USB%20keyboard%20%2B%20mouse-8b5cf6">
  <a href="https://github.com/premohq/PS5-ARTCRAFT/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/premohq/PS5-ARTCRAFT/actions/workflows/ci.yml/badge.svg"></a>
  <a href="#licences"><img alt="Licence: GPL-3.0-or-later" src="https://img.shields.io/badge/licence-GPL--3.0--or--later-a9a6ff"></a>
</p>

<p align="center">
  <b>PS5-ArtCraft</b> puts the Craft App Suite on a jailbroken PS5: PhotoCraft, VectorCraft, FilmCraft and ten more,<br>
  on a desktop of their own with a file manager, a USB keyboard and mouse, and ArtCraft Launcher starting by itself<br>
  and keeping itself and the apps up to date, as it does on a PC. Built on a fork of <a href="https://github.com/premohq/PS5_MihawkOS">Mihawk OS</a>,
  which runs Windows programs on the PS5 through Wine and Proton.<br>
  ArtCraft is a PS5 title of its own, <b>PPSA99278</b>, beside Mihawk OS and sharing nothing with it.
</p>

<p align="center">
  <a href="https://premohq.github.io/PS5-ARTCRAFT/"><b>Website</b></a> ·
  <a href="https://github.com/premohq/PS5-ARTCRAFT/releases"><b>Download</b></a> ·
  <a href="#put-it-on-the-console">Put it on the console</a> ·
  <a href="#build-it">Build it</a> ·
  <a href="#the-suite">The suite</a> ·
  <a href="#what-is-proven">What is proven</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="docs/ROADMAP.md">Roadmap</a> ·
  <a href="#support">Support</a> ·
  <a href="#credits">Credits</a>
</p>

---

> **Status:** work in progress. The whole edition builds from the real releases and runs under Wine on a PC, from the
> session start to the launcher to an app; the title and its runtime build in a pinned container; nothing has run on a
> console yet. [What is proven](#what-is-proven) says what has been checked, and how.

## Support

PS5-ARTCRAFT is free. If it brings ArtCraft to your PS5, you can support it:

- **Ko-fi:** [ko-fi.com/premohq](https://ko-fi.com/premohq), for a one-off tip or the
  [$3 a month Early Access tier](https://ko-fi.com/premohq/tiers).
- **PayPal:** [paypal.me/empthe](https://www.paypal.com/paypalme/empthe), or scan the code:

<a href="https://www.paypal.com/paypalme/empthe"><img src="docs/support-qr.svg" width="120" alt="QR code for paypal.me/empthe"></a>

## The suite

Every app ArtCraft Launcher's catalog lists, each installed the way the launcher installs a portable app, so it
adopts them and updates them in place. The pinned versions are in [`edition/suite.lock.json`](edition/suite.lock.json).

| | App | For | |
|---|---|---|---|
| <img src="assets/app-icons/photocraft.png" width="40" alt=""> | **PhotoCraft** | Image editing | [storytold/photocraft](https://github.com/storytold/photocraft) |
| <img src="assets/app-icons/vectorcraft.png" width="40" alt=""> | **VectorCraft** | Vector illustration | [storytold/vectorcraft](https://github.com/storytold/vectorcraft) |
| <img src="assets/app-icons/filmcraft.png" width="40" alt=""> | **FilmCraft** | Video editing, color and sound | [storytold/filmcraft](https://github.com/storytold/filmcraft) |
| <img src="assets/app-icons/lightcraft.png" width="40" alt=""> | **LightCraft** | Photo library and raw development | [storytold/lightcraft](https://github.com/storytold/lightcraft) |
| <img src="assets/app-icons/pdfcraft.png" width="40" alt=""> | **PdfCraft** | Reading, organizing and protecting PDFs | [storytold/pdfcraft](https://github.com/storytold/pdfcraft) |
| <img src="assets/app-icons/effectcraft.png" width="40" alt=""> | **EffectCraft** | Motion graphics and visual effects | [storytold/effectcraft](https://github.com/storytold/effectcraft) |
| <img src="assets/app-icons/designcraft.png" width="40" alt=""> | **DesignCraft** | Page layout and publishing | [storytold/designcraft](https://github.com/storytold/designcraft) |
| <img src="assets/app-icons/figcraft.png" width="40" alt=""> | **FigCraft** | Interface design and prototyping | [storytold/figcraft](https://github.com/storytold/figcraft) |
| <img src="assets/app-icons/wordcraft.png" width="40" alt=""> | **WordCraft** | Writing and document design | [storytold/wordcraft](https://github.com/storytold/wordcraft) |
| <img src="assets/app-icons/soundcraft.png" width="40" alt=""> | **SoundCraft** | Recording, editing and mixing audio | [storytold/soundcraft](https://github.com/storytold/soundcraft) |
| <img src="assets/app-icons/deckcraft.png" width="40" alt=""> | **DeckCraft** | Presentations and slide shows | [storytold/deckcraft](https://github.com/storytold/deckcraft) |
| <img src="assets/app-icons/cadcraft.png" width="40" alt=""> | **CADCraft** | Computer-aided design and drafting | [storytold/cadcraft](https://github.com/storytold/cadcraft) |
| <img src="assets/app-icons/gridcraft.png" width="40" alt=""> | **GridCraft** | Spreadsheets and data | [storytold/gridcraft](https://github.com/storytold/gridcraft) |

<p align="center">
  <img src="docs/screenshots/launcher-window-wine.png" width="49%" alt="ArtCraft Launcher listing the staged apps as installed, each with an Open button at its pinned version">
  <img src="docs/screenshots/cadcraft-window-wine.png" width="49%" alt="CADCraft open on an empty drawing">
  <br><sub>The staged edition under Wine 9.0 on a Linux PC: ArtCraft Launcher has adopted every app, and CADCraft opened from it.</sub>
</p>

## How it fits together

| Piece | Where | What it does |
|---|---|---|
| The title | `mihawk/patches/` on the fork at `mihawk/mihawk.lock.json` ([what each patch does](mihawk/README.md)) | A tile and a data folder of its own (PPSA99278, `/data/artcraft`) beside Mihawk OS, for the title, its runtime and the fork's install tools alike; boots straight into the ArtCraft desktop on a cold start (a session that ends shows the library, so a failing one never loops); its Start and taskbar keep only File Explorer and Settings; no MihawkBrowser shortcut; the Windows user is ArtCraft; everything the user reads says ArtCraft, with ArtCraft's own mark on the Start button and the PS5 tile, while the credits stay Mihawk's |
| The desktop | `artcraft_ps5/stage.py` | A prefix in ArtCraft's data folder (`/data/artcraft/prefixes/artcraft`): `C:\ArtCraft\Launcher` (ArtCraft Launcher, portable), `C:\ArtCraft\Apps\<app>` (each app, installed exactly as the launcher installs a portable ZIP, so the launcher adopts and updates them), the wallpaper, and the library entry that starts it |
| The session start | `session/artcraft-session.c` | Run by the desktop once it is up: imports the registry the launcher's self-update needs, applies the wallpaper and Start pins once, keeps a desktop shortcut per installed app, sets `WGPU_BACKEND=vulkan`, starts the launcher |
| The pins | `edition/suite.lock.json`, `mihawk/mihawk.lock.json` | Every release the edition installs, by version, URL, size and SHA-256; the fork's commit and the root-access daemon built for ArtCraft's title |
| The build | `build/Dockerfile`, `build/build.sh` | The fork's whole build, the title and its Wine runtime, in a container with every tool at its pinned version |
| The tools | `python3 -m artcraft_ps5` | Pin, fetch, draw, stage and deploy, and prepare the fork, below |

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) goes through each piece and the paths it writes on the console.

## Put it on the console

Download the newest build from [Releases](https://github.com/premohq/PS5-ARTCRAFT/releases) (or [build it](#build-it)):
`ArtCraft-PPSA99278.zip`, `ArtCraft-usb.zip` and `ArtCraft-desktop.zip`, with a `README.txt` of these steps. The
console runs homebrew as the Mihawk OS fork's README describes (its payloads, and your own ShadowMountPlus) and serves
FTP on port 2121. Mihawk OS, if installed, is left as it is.

1. Copy the title folder `PPSA99278` into `/data/homebrew` over FTP. The ArtCraft tile appears within about 45 seconds.
2. Copy `usb/artcraft` (in `ArtCraft-usb.zip`) to the root of a USB stick (exFAT or FAT32, MBR) and plug it in.
3. Open ArtCraft. Its guided setup installs the runtime from the stick and makes its folder, `/data/artcraft`. Then
   close it.
4. Send the ArtCraft desktop: upload the `data` folder of `ArtCraft-desktop.zip` to the console's root, merging into
   `/data`, with any FTP client; or from a build of your own, `python3 -m artcraft_ps5 deploy` (below). Do this after
   step 3, never before: ArtCraft makes `/data/artcraft` itself on its first start.
5. Open ArtCraft again: it starts its own desktop, and ArtCraft Launcher starts by itself.

`deploy` sends only what changed. The first deploy sends everything (about 1.25 GB). After that ArtCraft Launcher owns
itself and the apps and updates them as on a PC, so later deploys send only the edition's own files: the session
helper, its settings, the registry files, the wallpaper and the library entry. Install more apps from the launcher;
`deploy --force` re-sends everything as a repair. Close ArtCraft before a deploy. On the console, test in the order
of [docs/console-checklist.md](docs/console-checklist.md).

## Build it

The [Build ArtCraft](https://github.com/premohq/PS5-ARTCRAFT/actions/workflows/build.yml) workflow builds everything
on GitHub and publishes it to Releases. To build it yourself you need Docker (Docker Engine on Linux, or Docker Desktop
on Windows or macOS), about 60 GB free and a few hours: the build compiles Wine three times. Everything else is in the
container, at pinned versions.

```sh
git clone https://github.com/premohq/PS5-ARTCRAFT && cd PS5-ARTCRAFT
docker build -t artcraft-build build
docker run --rm -it -v artcraft-work:/work -v "$PWD":/src artcraft-build      # PowerShell: -v "${PWD}:/src"
build/package-release.sh release                                                # the three ZIPs of a release
```

`build/build.sh` runs inside: the Mihawk OS fork at its pin with ArtCraft's patches, its sibling sources, the fork's
own build (`tools/fetch-all.sh`, `tools/build-production.sh`), and the ArtCraft desktop. Running it again resumes. The
result is `out/package/` (the title folder and the runtime's pieces) and `dist/artcraft/` (the desktop). On an Arch
Linux PC with the packages `build/Dockerfile` installs, `WORK=~/artcraft-build build/build.sh` does the same without
Docker. To send the desktop from the container:

```sh
docker run --rm -it -v artcraft-work:/work -v "$PWD":/src -e PS5_HOST=<console address> artcraft-build \
    python3 -m artcraft_ps5 deploy
```

| Command | What it does |
|---|---|
| `python3 -m artcraft_ps5 show` | The edition, the suite, what is pinned and what the console gets |
| `python3 -m artcraft_ps5 lock [--refresh [--dry-run]] [--pin ID=VERSION ...]` | The pins; `--refresh` pins every app's newest release from its `SHA256SUMS.txt` (no API quota), `--dry-run` only lists them; `--pin` pins chosen releases and keeps the rest (an older launcher or app on a fresh console shows its update working) |
| `python3 -m artcraft_ps5 fetch [--apps ID ...]` | Downloads the pinned releases into `.deps/downloads`, resuming, each checked against its SHA-256 |
| `python3 -m artcraft_ps5 wallpaper [--out FILE]` | Draws the desktop wallpaper (BMP for Wine; a `.png` path gives a preview) |
| `python3 -m artcraft_ps5 icon [--out FILE]` | Draws the title's 512×512 icon |
| `python3 -m artcraft_ps5 stage [--apps ID ...] [--include-cli] [--clean]` | Lays out everything the console gets in `dist/artcraft`, at the console's own paths, with a manifest |
| `python3 -m artcraft_ps5 build` | `fetch`, `wallpaper` (once) and `stage` |
| `python3 -m artcraft_ps5 deploy [--dry-run] [--force]` | Sends `dist/artcraft` to the console over FTP: only what changed, and the launcher and the apps once |
| `python3 -m artcraft_ps5 mihawk prepare\|rebrand\|mark\|identity [--dir DIR]` | The fork at its pin with `mihawk/patches` applied (branch `artcraft`), or patches 0005 to 0007 regenerated after a rebase ([mihawk/README.md](mihawk/README.md)) |

`SOURCE_DATE_EPOCH` makes two stagings of the same pins identical. `python3 -m pytest tests` runs the tests.

## What is proven

- **The whole build of the edition, on the real releases:** `build` downloaded and verified all 14 pinned releases
  (1.04 GB) and staged 194 files (1.25 GB). The code-signing root came out of the launcher's real signature and matched
  its pin.
- **The edition under Wine 9.0 on Linux**, with Mesa's software Vulkan driver: `artcraft-session.exe` imported both
  registry files, wrote the 14 desktop shortcuts, set `WGPU_BACKEND=vulkan` and started ArtCraft Launcher. The
  launcher listed all 13 apps as installed (*Open*, at their pinned versions, none to install) and checked for
  updates; CADCraft opened from it and ran ([screenshots](#the-suite)). The session helper was also checked under
  GE-Proton 11-7's Wine 11.0, the archive the fork pins: registry, shortcuts (only for installed programs, left alone
  the second time), environment, launcher start.
- **ArtCraft Launcher reads what the edition seeds**, with its own types: CI builds the pinned launcher from source
  and reads the staged `installed.json` and `app.ron` with them.
- **The suite's releases:** all 13 apps and the launcher ship `<app>-<version>-windows-x64-portable.zip` with a
  `SHA256SUMS.txt`; each ZIP holds `<app>.exe` and `<app>-cli.exe` in a version-named folder. All of them are eframe
  0.36 / wgpu 30 apps that honour `WGPU_BACKEND`.
- **The launcher's self-update signature check** (`WinVerifyTrust`, as `verifysign` calls it), on the real launcher
  under Wine 9.0 and GE-Proton 11-7's Wine 11.0: the edition's `trust.reg` puts the Microsoft Identity Verification
  Root 2020 (taken from the launcher's own signature, pinned by SHA-256) in the user's Root store, where both keep it,
  and the signer chain's root is trusted (status 0x1: only the end certificate's expiry, as Wine reads no RFC 3161
  timestamp, and the `WTPF_IGNOREEXPIRATION` policy covers that). The machine's Root store would not do on Wine 9.0:
  its crypt32 deletes a root there that the host lacks before the first chain is built. Without the root, Wine still
  answers *trusted* (it fails open, status 0x21), so `artcraft-session.exe --check-signature` also logs the chain's
  status. An unsigned or tampered file is refused either way.
- **ArtCraft's own title:** patch 0007 changes only the title id and the data folder, in the files that name them, and
  the root-access daemon's pin. Each file reverses byte for byte to the fork's own text when the two values are
  swapped back, the daemon pin aside. The daemon is built for ArtCraft's title with clang/LLD 23.1.3 as Arch Linux
  packages them, which rebuilds Mihawk OS's pinned daemon byte for byte (`.github/workflows/daemon.yml`). The fork's
  Python tests (148) and host tests have the same outcome as before it. `deploy` refuses to write anything under
  Mihawk OS's title or data folder.
- **The build container** (`build/Dockerfile`, the Build environment workflow): it builds; the sources check out at
  their pins with the eight patches; every pinned input of the fork's build answers at its URL (the one that no longer
  did, the PS5 OpenGL SDK, is patch 0008's mirror); and it builds PS5_Vulkan's `libc.prx` (reproducibly, matching its
  pin) and native tool, the first things the title's build needs.
- **The fork patches** (CI applies them at the pin and runs the fork's host tests on every push): the title code
  compiles in the host-reference configuration, as PPSA99278; the shell changes compile with MinGW in a mock; the
  profile move passes the fork's own host test, extended for MihawkOS v3 prefixes, under ASan and UBSan, as root and as
  a user. None has run on a console.
- **The tools:** 139 tests (`python3 -m pytest tests`) cover the edition's checks, pinning and downloads, the portable
  installs, the registry, launcher-state and signature formats, staging, the FTP deploy and its one-time seed, the
  fork's rebrand and identity, and the command line.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): each piece, what it writes where, and why
- [Roadmap](docs/ROADMAP.md): what is left before a release
- [Console checklist](docs/console-checklist.md): the first run on a PS5, step by step, and where to look when one fails
- [The fork's patches](mihawk/README.md): what each one changes, how it is proven, and how to regenerate them

## Credits

### Built on

- [Mihawk OS](https://github.com/mihawk-99/PS5_MihawkOS) by Mihawk and its contributors (GPL-3.0-or-later), through
  [premohq's fork](https://github.com/premohq/PS5_MihawkOS), with Wine and Proton
- The Craft App Suite and [ArtCraft Launcher](https://github.com/storytold/craft-launcher) by the ArtCraft Team and
  each app's contributors (MIT OR Apache-2.0): the edition installs their official releases
- The README art is set in Archivo, Inter and Geist Mono (SIL OFL 1.1), the typefaces ArtCraft Launcher uses

## Brand assets

| File | Size | Use |
| --- | --- | --- |
| [`assets/banner.png`](assets/banner.png) | 2560×640 | README header |
| [`assets/social-preview.png`](assets/social-preview.png) | 1280×640 | Repo social preview (Settings → General → Social preview) |
| [`assets/icon.png`](assets/icon.png) | 512×512 | Repository icon / avatar |
| [`assets/app-icons/`](assets/app-icons/) | 256×256 | Each app's own icon, from its release ([attribution](assets/app-icons/ATTRIBUTION.md)) |

They are drawn in ArtCraft Launcher's own look from [`assets/src/`](assets/src/): `python3 assets/extract.py` takes
the app icons and the launcher's typefaces out of the downloaded releases, and `node assets/render.cjs` renders the
pages with Playwright's Chromium.

## Licences

The patches modify GPL-3.0-or-later code from Mihawk OS (Copyright (C) 2026 Mihawk and the authors credited in its
NOTICE.md). The Craft apps and ArtCraft Launcher are MIT or Apache-2.0, by the ArtCraft Team; this repository
downloads their official releases and does not redistribute them, apart from each app's icon in `assets/app-icons/`,
under that app's licence. The ArtCraft name, wordmark and "A" mark are trademarks of the ArtCraft Team and are not
used here.
