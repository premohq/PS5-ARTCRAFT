# PS5-ARTCRAFT

The Craft App Suite (PhotoCraft, VectorCraft, FilmCraft, LightCraft, PdfCraft, EffectCraft, DesignCraft, FigCraft,
WordCraft, SoundCraft, DeckCraft, CADCraft, GridCraft) on a jailbroken PS5, on a closed desktop of its own with a file
manager, USB keyboard and mouse, a themed wallpaper, and ArtCraft Launcher starting by itself and updating itself and
the apps as it does on a PC. Built on a fork of [Mihawk OS](https://github.com/premohq/PS5_MihawkOS), which runs
Windows programs on the PS5 through Wine and Proton's stack.

ArtCraft is a PS5 title of its own, **PPSA99278**, with everything it keeps in **`/data/artcraft`**. It installs
beside Mihawk OS (PPSA99170, `/data/ps5proton`) and shares nothing with it: not the tile, the Wine runtime, the
prefixes, the library or the logs. Both can be installed at once, and installing, updating or removing one leaves the
other as it was. The cost is disk space: ArtCraft brings its own copy of the runtime (about 1.2 GB).

> Status: work in progress, nothing here has run on a console yet. What has been checked, and how, is listed under
> [What is proven](#what-is-proven).

## How it fits together

| Piece | Where | What it does |
|---|---|---|
| The title | `mihawk/patches/` on the fork at `mihawk/mihawk.lock.json` ([what each patch does](mihawk/README.md)) | Its own tile and data folder (PPSA99278, `/data/artcraft`), for the title, its runtime and the fork's install tools alike; boots straight into the ArtCraft desktop on a cold start (a session that ends shows the library, so a failing one never loops); its Start and taskbar keep only File Explorer and Settings; no MihawkBrowser shortcut; the Windows user is ArtCraft (older Mihawk and steamuser profiles move to it with their saves); everything the user reads says ArtCraft, with ArtCraft's own mark on the Start button and the PS5 tile, while the credits stay Mihawk's |
| The desktop | `artcraft_ps5/stage.py` | A prefix in ArtCraft's data folder (`/data/artcraft/prefixes/artcraft`): `C:\ArtCraft\Launcher` (ArtCraft Launcher, portable), `C:\ArtCraft\Apps\<app>` (each app, installed exactly as the launcher installs a portable ZIP, so the launcher adopts and updates them), the wallpaper, and the library entry that starts it |
| The session start | `session/artcraft-session.c` | Run by the desktop once it is up: installs the code-signing root and policy the launcher's self-update needs, applies the wallpaper and Start pins once, keeps a desktop shortcut per installed app, sets `WGPU_BACKEND=vulkan`, starts the launcher |
| The pins | `edition/suite.lock.json` | Every release the edition installs, by version, URL, size and SHA-256 |

## On the PC

### Build (once; hours the first time)

You need Docker (Docker Engine on Linux, or Docker Desktop on Windows or macOS), about 60 GB free and a few hours: the
build compiles Wine three times. Everything else is in the container, at pinned versions.

```sh
git clone -b claude/tender-fermat-z3l05c https://github.com/premohq/PS5-ARTCRAFT && cd PS5-ARTCRAFT
docker build -t artcraft-build build
docker run --rm -it -v artcraft-work:/work -v "$PWD":/src artcraft-build      # PowerShell: -v "${PWD}:/src"
```

`build/build.sh` runs inside: the Mihawk OS fork at its pin with ArtCraft's patches, its sibling sources, the fork's
own build (`tools/fetch-all.sh`, `tools/build-production.sh`), and the ArtCraft desktop. Running it again resumes. The
result is in this checkout:

- `out/package/`: the ArtCraft title folder `PPSA99278` and `usb/artcraft/`, the Windows runtime's pieces, with a
  `README.txt`;
- `dist/artcraft/`: the ArtCraft desktop (ArtCraft Launcher, the 13 apps, the session helper, the wallpaper).

On an Arch Linux PC with the packages `build/Dockerfile` installs, `WORK=~/artcraft-build build/build.sh` does the
same without Docker.

### Install on the console

The console runs homebrew as the fork's README describes (its payloads, and your own ShadowMountPlus) and serves FTP on
port 2121. Mihawk OS, if installed, is left as it is.

1. Copy `out/package/PPSA99278` into `/data/homebrew` over FTP. The ArtCraft tile appears within about 45 seconds.
2. Copy the contents of `out/package/usb/` to a USB stick (exFAT or FAT32, MBR) and plug it into the console.
3. Open ArtCraft. Its guided setup installs the runtime from the stick and makes its folder, `/data/artcraft`. Then
   close it.
4. Send the ArtCraft desktop:

   ```sh
   docker run --rm -it -v artcraft-work:/work -v "$PWD":/src -e PS5_HOST=<console address> artcraft-build \
       python3 -m artcraft_ps5 deploy
   ```

5. Open ArtCraft again: it starts its own desktop, and ArtCraft Launcher starts by itself.

Close ArtCraft before a deploy. The first deploy sends everything (about 1.25 GB). After that ArtCraft Launcher owns
itself and the apps and updates them as on a PC, so later deploys send only the edition's own files: the session
helper, its settings, the registry files, the wallpaper and the library entry. Install more apps from the launcher;
`deploy --force` re-sends everything as a repair. `python3 -m artcraft_ps5 lock --refresh` pins the newest releases
for the next fresh console.

On the console, test in the order of [docs/console-checklist.md](docs/console-checklist.md).

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
- ArtCraft's own title: patch 0007 changes only the title id and the data folder, in the files that name them, and
  the root-access daemon's pin. Each file reverses byte for byte to the fork's own text when the two values are
  swapped back, the daemon pin aside. The daemon is built for ArtCraft's title with clang/LLD 23.1.3 as Arch Linux
  packages them, which rebuilds Mihawk OS's pinned daemon byte for byte (`.github/workflows/daemon.yml`). The fork's
  Python tests (148) and host tests have the same outcome as before it. `deploy` refuses to write anything under
  Mihawk OS's title or data folder.
- The PC build's container (`build/Dockerfile`, CI's Build environment workflow): it builds; the sources check out at
  their pins with the eight patches; every pinned input of the fork's build answers at its URL (the one that no longer
  did, the PS5 OpenGL SDK, is patch 0008's mirror); and it builds PS5_Vulkan's `libc.prx` (reproducibly, matching its
  pin) and native tool, the first things the title's build needs. The hours-long Wine builds after that have not run.
- The fork patches (CI applies them at the pin and runs the fork's host tests on every push): the title code
  compiles in the host-reference configuration, as PPSA99278; the shell changes compile with MinGW in a mock; the profile move
  passes the fork's own host test, extended for MihawkOS v3 prefixes, under ASan and UBSan, as root and as a user.
  None has run on a console.

## Licences

The patches modify GPL-3.0-or-later code from Mihawk OS (Copyright (C) 2026 Mihawk and the authors credited in its
NOTICE.md). The Craft apps and ArtCraft Launcher are MIT or Apache-2.0, by the ArtCraft team; this repository
downloads their official releases and does not redistribute them. The ArtCraft name and marks belong to their owners.
