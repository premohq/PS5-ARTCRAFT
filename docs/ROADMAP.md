# Roadmap

What is left before a first release, roughly in order. [What is proven](../README.md#what-is-proven) says what already
works and how it was checked.

## 1. The first console run

Nothing has run on a PS5 yet. The edition builds from the real releases and runs under Wine 9.0 on a Linux PC, from
the session start through the launcher to an app. The next step is the same run on the console:

1. Build the title and its runtime with the eight patches (the Build ArtCraft workflow, or `build/build.sh` in the
   build container), and install them as README.md's Put it on the console says. They compile, but the fork's gate
   battery has not seen them.
2. Send the desktop (`python3 -m artcraft_ps5 deploy`, or the release's `ArtCraft-desktop.zip` over FTP).
3. Start the ArtCraft title and read `C:\ArtCraft\System\logs\session.log`.
   [docs/console-checklist.md](console-checklist.md) goes through the whole first run.

Things to watch on that first run:

- **The cold start:** the title should open the ArtCraft desktop, and a session that ends should come back to the
  library.
- **The launcher and the apps on the PS5's Vulkan driver:** all of them are eframe/wgpu programs started with
  `WGPU_BACKEND=vulkan`.
- **USB keyboard and mouse** in the launcher and the apps.
- **The launcher's first update check** from the console, and a self-update.
- **The code-signing root:** `artcraft-session.exe --check-signature C:\ArtCraft\Launcher\artcraft-launcher.exe`
  should log *the root is trusted* (signer chain status 0x1), as it does under Wine 9.0 and 11.0 on a PC.

## 2. A title of its own: done

ArtCraft is `PPSA99278` with its own `/data/artcraft` (patch 0007, made by `artcraft_ps5/identity.py`): the title, its
runtime, the root-access daemon (built for that title and pinned, `.github/workflows/daemon.yml`) and the fork's
install tools all use them, and Mihawk OS stays installed beside it. The tile carries ArtCraft's mark (patch 0006).
What is left is the console run: both titles installed, each opening its own desktop
([docs/console-checklist.md](console-checklist.md), section 9).

## 3. A release

The Build ArtCraft workflow builds a release on GitHub and publishes three ZIPs (the title folder, the USB runtime
and the desktop, the session helper prebuilt inside it) with the steps to install them. Once a console run works, one
of them becomes the first release proper.

The repository also needs a licence of its own. The patches and the session helper are GPL-3.0-or-later, as Mihawk OS
is, and the Python tools carry no licence statement yet.

## Smaller things

- The wallpaper is drawn at 1920×1080. The desktop's real size on the console should decide that.
