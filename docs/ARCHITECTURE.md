# Architecture

The ArtCraft edition is Mihawk OS with a desktop of its own. Mihawk OS runs Windows programs on a jailbroken PS5
through Wine and Proton, each library entry in a Wine prefix; the edition adds one entry, `artcraft`, whose prefix
holds ArtCraft Launcher and the Craft App Suite, and teaches the title to open that entry's desktop by itself. Nothing
in the apps is changed: they are the official Windows releases, installed the way ArtCraft Launcher installs them, so
the launcher keeps them up to date on the console as it does on a PC.

```
PC                                                    PS5 (jailbroken, the fork's title PPSA99170)
edition/*.json ─┐                                     /data/homebrew/PPSA99170/edition.json ─► title opens the
GitHub releases ┼─► python3 -m artcraft_ps5 build ─►  /data/ps5proton/games/artcraft/game.json   artcraft desktop
session/*.c ────┘    (fetch, wallpaper, stage)        /data/ps5proton/prefixes/artcraft/drive_c/ArtCraft/
                     dist/artcraft ── deploy (FTP) ─►     System/artcraft-session.exe ─► starts the launcher
                                                          Launcher/, Apps/<id>/, Theme/
```

## The edition: `edition/`

| File | What it says |
|---|---|
| `edition.json` | The title slot (`PPSA99170`), the library entry and prefix (`artcraft`), the Windows root (`C:\ArtCraft`), which apps to seed, the environment the apps get (`WGPU_BACKEND=vulkan`), the launcher's settings, the code-signing root to pin, the wallpaper's theme and seed |
| `suite.json` | The suite as ArtCraft Launcher's catalog names it: each app's id (release asset stem, the launcher's record key and its folder name), name, tagline, repository and colour |
| `suite.lock.json` | Every release the edition installs, by version, tag, asset, URL, size and SHA-256 |

`artcraft_ps5/edition.py` reads all three once and checks them, so every other step works from typed values. What it
refuses, and why:

- **The root:** an absolute `C:\` path in ASCII without spaces, because the title splits `launch.args` on spaces and
  writes shortcut targets as 7-bit ASCII.
- **The prefix:** one of its own, never `mihawk`, so the edition and Mihawk OS's desktop never share a Windows
  install.
- **The environment:** no `PROTON_`, `MIHAWK_` or `WINE_PS5_NTSYNC` names, because the title keeps those for itself.
- **The launcher settings:** only the values the launcher understands (`check_every`, `preferred_kinds`).
- **The lock:** a pin for every app in the suite and none for anything else.

## Pinning and fetching: `releases.py`

Every app publishes `<id>-<version>-windows-x64-portable.zip` and a `SHA256SUMS.txt` on each release. `lock --refresh`
reads `releases/latest/download/SHA256SUMS.txt` for each app (a redirect, so no GitHub API call and no quota, as the
launcher itself does) and probes each ZIP with a one-byte range request for its size. `fetch` downloads into
`.deps/downloads`, resumes a partial file, and accepts a file only when its size and SHA-256 match the pin.

## Installing as the launcher does: `portable.py`, `launcher_state.py`

The launcher adopts an app it finds recorded in its own state. `portable.py` follows
`storytold/craft-launcher`'s `crates/native/src/portable.rs`: the app's folder is named by its id, the release's one
wrapper folder is flattened, unsafe paths and links are refused, and every file installed is recorded as an absolute
Windows path. The `-cli.exe` builds (about 1.1 GB the console never runs) are left out and left unrecorded, so a later
update by the launcher brings them back as it would on a PC.

`launcher_state.py` writes the two files the launcher reads from its portable data folder before it ever runs:
`installed.json` (the records) and `app.ron` (its settings in eframe's storage format: install new apps under
`C:\ArtCraft\Apps`, update automatically, prefer portable ZIPs).

## Staging: `stage.py`

`stage` lays out everything the console gets under one folder whose paths are the console's own:

| Path on the console | What it is |
|---|---|
| `/data/ps5proton/prefixes/artcraft/drive_c/ArtCraft/Launcher/` | ArtCraft Launcher's portable copy, `portable.txt` beside it, its seeded `ArtCraftLauncherData` |
| `…/ArtCraft/Apps/<id>/` | Each app, unpacked as the launcher unpacks one |
| `…/ArtCraft/System/` | `artcraft-session.exe`, `session.ini`, `trust.reg`, `defaults.reg` |
| `…/ArtCraft/Theme/` | The wallpaper, a 24-bit BMP |
| `/data/ps5proton/games/artcraft/game.json` | The library entry: the desktop session in the `artcraft` prefix, with the session helper as its argument |
| `/data/homebrew/PPSA99170/edition.json` | Tells the patched title which entry to open at a cold start |
| `manifest.json` (not sent) | Every file's console path, size and SHA-256 |

Nothing is staged under `drive_c/windows`: `wineboot` makes that folder, and one made before it breaks a new prefix.

The registry files are UTF-16 `regedit` files (`regfile.py`):

- `trust.reg` holds the code-signing root, taken out of the launcher's own Authenticode signature by `authenticode.py`
  and checked against its pin, plus the `WTPF_IGNOREEXPIRATION` WinTrust policy.
- `defaults.reg` holds the wallpaper, the Start pins (File Explorer, the launcher, then the seeded apps) and
  `BrowserPinned`, so MihawkBrowser is never pinned.

## The session start: `session/artcraft-session.c`

The desktop runs it once Explorer is up. It:

1. imports `trust.reg` at every start;
2. imports `defaults.reg` once per version of it (the version is a hash, remembered in `HKCU\Software\ArtCraft\Session`),
   so what the user changes afterwards stays;
3. keeps one desktop shortcut per installed program in `[shortcuts]`, removing only shortcuts it made whose program is
   gone;
4. sets `[environment]` for everything it starts;
5. starts ArtCraft Launcher. The launcher is single-instance, so a second start only shows its window.

It logs to `System\logs\session.log`, as there is no console to read. `--check-signature FILE` makes the same
`WinVerifyTrust` call the launcher's self-update makes.

## The title: `mihawk/patches/`

Four patches on the fork at the commit in `mihawk/mihawk.lock.json`, applied with `git am`:

1. **`ps5`:** the title reads `edition.json` from its folder. A cold start opens the edition's entry; a return from a
   session shows the library, so a failing session never loops. Mihawk OS's own desktop entry is hidden once the
   edition's is installed.
2. **`native`:** the edition's desktop can leave out the MihawkBrowser shortcut.
3. **`explorer`:** Start and the taskbar keep only File Explorer and Settings.
4. **`wine`:** the Windows user is ArtCraft. Mihawk and steamuser profiles from earlier prefixes move to it, saves
   kept.

## Deploying: `deploy.py`

The deploy goes over FTP to the ftpsrv payload (port 2121). The console's address comes from `--host`, `PS5_HOST`, or
`../PS5_Vulkan/.env`, and is only ever printed masked. The deploy:

- turns ftpsrv's SELF decryption off first;
- writes each file as `.<name>.upload` and renames it into place;
- keeps a manifest of what it sent in the prefix folder, so the next deploy sends only what changed.
