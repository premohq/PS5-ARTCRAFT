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
| 0005 | Everything the user reads says ArtCraft (made by `artcraft_ps5/rebrand.py`); the USB folder is `artcraft/`; the log tag is `[ArtCraft]`; credits stay Mihawk's | setup (9 languages, every glyph drawable), detailed-logs and package host tests |
| 0006 | ArtCraft's mark on the Start button and the PS5 tile (made by `artcraft_ps5/mark.py`) | the fork's logo and icon tests against librsvg |

None has run on a console: the fork's commit gate (`tools/gate.py`) is still to pass on a build of them.

## After rebasing onto a newer Mihawk OS

0005 and 0006 are generated, so regenerate them rather than resolving conflicts in them by hand: apply 0001 to 0004,
then

```sh
python3 -m artcraft_ps5 mihawk rebrand  # stops, naming the file, if a string moved
git -C ../PS5_MihawkOS commit -a        # 0005
python3 -m artcraft_ps5 mihawk mark
git -C ../PS5_MihawkOS commit -a        # 0006 (fix up tests/test_taskbar_logo.py and test_title_icon.py as 0006 does)
git -C ../PS5_MihawkOS format-patch --binary --no-numbered <pin>..HEAD -o "$PWD"/mihawk/patches
```
