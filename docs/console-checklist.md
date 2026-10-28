# Testing the ArtCraft edition on a console

Nothing here has run on a PS5 yet. Work through this in order on a console that has the fork's title and runtime
installed (the fork's README; its commit gate, `tools/gate.py`, should pass on the patched build first). Each step
names what to look for and where to read what went wrong.

Where to look:

- The session helper's log: `/data/ps5proton/prefixes/artcraft/drive_c/ArtCraft/System/logs/session.log` (FTP),
  one line per thing it did: `trust:`, `defaults:`, `wallpaper:`, `shortcuts:`, `environment:`, `launcher:`.
- The title's log, whose lines are tagged `[ArtCraft]`: the fork's `tools/run-console.py` reads it.
- The launcher's own state: `.../drive_c/ArtCraft/Launcher/ArtCraftLauncherData/` (`data/installed.json`,
  `data/app.ron`).

## 1. First deploy: start one release behind, so the updates have something to do

The launcher updating itself is the part most worth seeing. Pin it, and one small app, one release back for the
first deploy only. Both releases read the same `installed.json` and settings as the current ones, and 0.7.0 updates
itself the same way 0.8.1 does.

```sh
python3 -m artcraft_ps5 lock --pin artcraft-launcher=0.7.0 soundcraft=0.12.1
python3 -m artcraft_ps5 fetch && rm -rf dist/artcraft && python3 -m artcraft_ps5 stage
python3 -m artcraft_ps5 deploy            # close the title first; about 1.25 GB the first time
git checkout edition/suite.lock.json      # back to the current pins
```

- [ ] `deploy` ends with `done: <n> sent` and no error, and a second `deploy` straight after sends only what changed.

## 2. The title

- [ ] The tile says ArtCraft and shows ArtCraft's mark, not Mihawk OS's.
- [ ] A cold start of a fresh install runs the guided setup, which says ArtCraft in every language it offers.
- [ ] After setup, or on any later cold start, the title goes straight to the ArtCraft desktop with no library first.
- [ ] Quit the desktop: the title shows its library rather than reopening the desktop, so a failing session never
      loops. Its About page credits Mihawk (a modified version of MihawkOS; the source repositories).

## 3. The desktop

- [ ] The wallpaper is ArtCraft's dark ribbons. `session.log`: `defaults: regedit /S ...: exit 0`, then
      `wallpaper: ... set`.
- [ ] Start's and the taskbar's own entries are File Explorer and Settings only, with no Notepad, Terminal or
      Browser. Start also pins ArtCraft Launcher and the 13 apps, and the desktop has no browser shortcut.
- [ ] The desktop has ArtCraft Launcher and the 13 apps. `session.log`: `shortcuts: 14 written`.
- [ ] Start's account row says ArtCraft, and File Explorer shows `C:\users\ArtCraft`.
- [ ] File Explorer opens `C:\ArtCraft` and a USB stick.
- [ ] A USB keyboard and mouse work everywhere: text fields, shortcuts, right click, scrolling.

## 4. ArtCraft Launcher starts by itself

- [ ] `session.log`: `environment: WGPU_BACKEND=vulkan`, then `launcher: started ...`.
- [ ] Its window draws (wgpu through winevulkan to RADV).
- [ ] It lists the 13 apps as installed at their pinned versions, with no Install buttons. If they show as not
      installed, `installed.json` was not read: keep a copy of it for the bug.
- [ ] Settings: updates automatic, notifications on, install folder `C:\ArtCraft\Apps`.
- [ ] Its catalog and release notes load. A TLS or certificate error here means crypt32's store, not the edition.

## 5. Updates, as on a PC

- [ ] The launcher offers or installs ArtCraft Launcher 0.8.1. It downloads it, checks its signature, closes, and
      comes back as 0.8.1 on its own.
      - If it refuses the download as unsigned or from another publisher, that is the `WinVerifyTrust` check. The
        edition installs the code-signing root and policy for it every session (`trust: regedit /S ...: exit 0`).
        Copy the downloaded file off the console and run `artcraft-session.exe --check-signature FILE` on it, under
        the same Wine, to get the status the launcher saw.
- [ ] After the restart it still lists all 13 apps as installed. `ArtCraftLauncherData` survived the update.
- [ ] SoundCraft updates from 0.12.1 to 0.13.1 in `C:\ArtCraft\Apps\soundcraft`, and its desktop shortcut still
      opens it.
- [ ] Quit and restart the title. The desktop comes back with launcher 0.8.1, and `session.log` says
      `defaults: ... already applied; the user's choices stay`.

## 6. The apps

For each app: it opens from its desktop shortcut and from the launcher, draws, takes keyboard and mouse input, saves a
file to Documents and opens it again.

- [ ] PhotoCraft · VectorCraft · FilmCraft · LightCraft · PdfCraft · EffectCraft · DesignCraft
- [ ] FigCraft · WordCraft · SoundCraft (audio out) · DeckCraft · CADCraft · GridCraft

## 7. The user's choices stay

- [ ] Change the wallpaper in Settings, unpin an app and change a launcher setting. Then restart the title: all three
      stay.
- [ ] Run `python3 -m artcraft_ps5 deploy` again. It reports `... launcher and app files left as ArtCraft Launcher
      keeps them`, sends almost nothing, and the launcher is still 0.8.1 afterwards.

## 8. Recovery

- [ ] Delete one app's folder from the console (FTP) and restart the title. Its desktop shortcut goes
      (`shortcuts: ... removed`). Note what the launcher shows for it (missing, or offered to install again), and
      reinstall it from there.
- [ ] `python3 -m artcraft_ps5 deploy --force` puts back the pinned launcher and apps, over whatever is there.
