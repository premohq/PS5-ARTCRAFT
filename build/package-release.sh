#!/usr/bin/env bash
# Package a finished build (build/build.sh) for download: what a console needs, as three ZIPs and the steps to use them.
#
#   build/package-release.sh OUT
#
#   OUT/ArtCraft-PPSA99278.zip   the title folder PPSA99278 (copy it into /data/homebrew)
#   OUT/ArtCraft-usb.zip         artcraft/, the Windows runtime's pieces (to the root of a USB stick)
#   OUT/ArtCraft-desktop.zip     data/, the ArtCraft desktop: ArtCraft Launcher, the apps, the session helper, the
#                                wallpaper (merge into the console's /data over FTP, after ArtCraft's first start)
#   OUT/README.txt, OUT/SHA256SUMS
set -euo pipefail
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out=$(mkdir -p "$1" && cd "$1" && pwd)
package=$src/out/package
desktop=$src/dist/artcraft
title=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["title"]["id"])' "$src/edition/edition.json")
for need in "$package/$title/eboot.bin" "$package/usb/artcraft" "$desktop/manifest.json" "$desktop/data"; do
    [[ -e $need ]] || { echo "$need is missing: run build/build.sh first" >&2; exit 1; }
done
rm -f "$out"/ArtCraft-*.zip "$out/SHA256SUMS" "$out/README.txt"
# -X: no extra file attributes, -y: links as links; the archives hold paths relative to where they are copied to.
(cd "$package" && zip -q -r -X -y "$out/ArtCraft-$title.zip" "$title")
(cd "$package/usb" && zip -q -r -X -y "$out/ArtCraft-usb.zip" artcraft)
(cd "$desktop" && zip -q -r -X -y "$out/ArtCraft-desktop.zip" data)
cat > "$out/README.txt" <<EOF
ArtCraft for PS5: the Craft App Suite on a desktop of its own (title $title, beside Mihawk OS, sharing nothing with it)
Built from https://github.com/premohq/PS5-ARTCRAFT at $(git -C "$src" rev-parse --short HEAD) by build/build.sh.

The console runs homebrew (kstuff, elfldr, websrv, ftpsrv, and your own ShadowMountPlus) and serves FTP on port 2121.

1. Unzip ArtCraft-$title.zip and copy the folder $title into /data/homebrew over FTP. The ArtCraft tile appears within
   about 45 seconds.
2. Unzip ArtCraft-usb.zip to the root of a USB stick (exFAT or FAT32, MBR partition table), so the stick holds an
   artcraft folder, and plug it into the console.
3. Open ArtCraft. Its guided setup installs the Windows runtime from the stick and makes /data/artcraft. Close it
   when it shows its library.
4. Unzip ArtCraft-desktop.zip and upload its data folder to the console's root over FTP, merging it into /data
   (any FTP client: the folders inside are artcraft and homebrew). It is about 1.3 GB. Do this after step 3, never
   before: ArtCraft makes /data/artcraft itself on its first start.
5. Open ArtCraft again: it starts its own desktop, and ArtCraft Launcher starts by itself and keeps itself and the
   apps up to date.

\`sha256sum -c SHA256SUMS\` in this folder checks the downloads. Mihawk OS, if installed, is left as it is.
EOF
(cd "$out" && sha256sum ArtCraft-*.zip README.txt > SHA256SUMS)
ls -l "$out"
