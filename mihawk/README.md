# The Mihawk OS fork's ArtCraft patches

`mihawk.lock.json` pins the fork ([premohq/PS5_MihawkOS](https://github.com/premohq/PS5_MihawkOS)) at the commit these
patches apply to. `python3 -m artcraft_ps5 mihawk prepare` clones it into ../PS5_MihawkOS (or `--dir`), checks
out the pin on a branch named artcraft and applies them with `git am`, as CI does on every push.

| Patch | What it changes | Proven |
|---|---|---|
| 0001 | The title reads `edition.json` from its folder and opens the edition's desktop at a cold start (a return from a session shows the library, so a failing one never loops); setup prepares that desktop; a library entry naming the session's `mihawk.exe` is no longer refused | host-reference compile; the new code against the real header in a mock |
| 0002 | `browser_shortcut: false` keeps MihawkBrowser off the edition's desktop | read only (needs the PS5 SDK) |
| 0003 | Start and the taskbar keep only File Explorer and Settings | MinGW compile of the changed code in a mock |
| 0004 | The Windows user is ArtCraft; a MihawkOS v3 (`Mihawk`) or alpha-2 (`steamuser`) profile moves to it with its saves, links and registry | the fork's profile host test, extended, under ASan and UBSan |
| 0005 | Everything the user reads says ArtCraft (made by `artcraft_ps5/rebrand.py`); the USB folder is `artcraft/` (a Mihawk OS stick's `mihawkos/` is not read: it holds Mihawk OS's runtime); the log tag is `[ArtCraft]`; credits stay Mihawk's | setup (9 languages, every glyph drawable), detailed-logs and package host tests |
| 0006 | ArtCraft's mark on the Start button and the PS5 tile (made by `artcraft_ps5/mark.py`) | the fork's logo and icon tests against librsvg |
| 0007 | A title of its own beside Mihawk OS: PPSA99278 and `/data/artcraft` everywhere the fork named PPSA99170 and `/data/ps5proton` (title, runtime, root daemon log, install tools and their tests; made by `artcraft_ps5/identity.py`, which refuses a tree with an update feed); the root-access daemon's pin is ArtCraft's build (`mihawk.lock.json`) | 103 files, each but the daemon pin reversing byte for byte when the values are swapped back; the daemon workflow rebuilds Mihawk OS's pinned daemon byte for byte and ArtCraft's to its pin; host tests as root and as a user; 148 Python tests, outcomes unchanged; host-reference compile as PPSA99278 |
| 0008 | The PS5 OpenGL SDK from its mirror, darkxex/ps5-opengl 1.0.2 (blackbearreloaded/ps5-opengl is gone, so 1.0.0 can no longer be fetched): exactly Mihawk OS v4.0.0-alpha-4's change | every OpenGL line the same as v4.0.0-alpha-4's; the archive matches its digest and holds the libraries and every licence text the build copies; `build.sh --check` finds every pinned input |

None has run on a console: the fork's commit gate (`tools/gate.py`) is still to pass on a build of them.

## After rebasing onto a newer Mihawk OS

0005 to 0007 are generated, so regenerate them rather than resolving conflicts in them by hand (0008 is a plain
port and goes after them): apply 0001 to 0004, then

```sh
python3 -m artcraft_ps5 mihawk rebrand  # stops, naming the file, if a string moved
git -C ../PS5_MihawkOS commit -a        # 0005
python3 -m artcraft_ps5 mihawk mark
git -C ../PS5_MihawkOS commit -a        # 0006 (fix up tests/test_taskbar_logo.py and test_title_icon.py as 0006 does)
python3 -m artcraft_ps5 mihawk identity # stops if a string moved or the tree names an update feed
git -C ../PS5_MihawkOS commit -a        # 0007
git -C ../PS5_MihawkOS format-patch --binary --no-numbered <pin>..HEAD -o "$PWD"/mihawk/patches
```
