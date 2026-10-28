# Roadmap

What is left before a first release, roughly in order. [What is proven](../README.md#what-is-proven) says what already
works and how it was checked.

## 1. The first console run

Nothing has run on a PS5 yet. The edition builds from the real releases and runs under Wine 9.0 on a Linux PC, from
the session start through the launcher to an app. The next step is the same run on the console:

1. Build and install the fork's title with the four patches. They compile, but the fork's gate battery has not seen
   them.
2. Run `python3 -m artcraft_ps5 build`, then `deploy`.
3. Start the ArtCraft title and read `C:\ArtCraft\System\logs\session.log`.

Things to watch on that first run:

- **The cold start:** the title should open the ArtCraft desktop, and a session that ends should come back to the
  library.
- **The launcher and the apps on the PS5's Vulkan driver:** all of them are eframe/wgpu programs started with
  `WGPU_BACKEND=vulkan`.
- **USB keyboard and mouse** in the launcher and the apps.
- **The launcher's first update check** from the console, and a self-update.
- **The code-signing root:** `artcraft-session.exe --check-signature C:\ArtCraft\Launcher\artcraft-launcher.exe`
  should log *the root is trusted* (signer chain status 0x1), as it does under Wine 9.0 and 11.0 on a PC.

## 2. A title of its own

The edition takes `PPSA99170`, Mihawk OS's slot, because the fork's tools (`console-setup.py`, `gate.py`,
`pack-runtime.py`, `package-install.py`) and ShadowMountPlus all name it. ArtCraft as a tile of its own beside Mihawk
OS needs:

- a new title id in `edition/edition.json`;
- those tools taught to read the id from there;
- the title's icon: `python3 -m artcraft_ps5 icon` already draws it, but nothing installs it yet.

## 3. A release

Once a console run works, a release should carry:

- a ZIP of `dist/artcraft` for people without the Python tools;
- the session helper prebuilt;
- notes on how to install it beside the fork's title.

The repository also needs a licence of its own. The patches and the session helper are GPL-3.0-or-later, as Mihawk OS
is, and the Python tools carry no licence statement yet.

## Smaller things

- The wallpaper is drawn at 1920×1080. The desktop's real size on the console should decide that.
