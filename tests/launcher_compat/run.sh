#!/bin/bash
# Read PS5-ARTCRAFT's seeded launcher files with ArtCraft Launcher's own types.
#   tests/launcher_compat/run.sh CRAFT_LAUNCHER_CHECKOUT STAGED_DIST [APP,APP,...]
# CRAFT_LAUNCHER_CHECKOUT: a clone of storytold/craft-launcher (the tests are copied into it and removed after).
# STAGED_DIST: the folder `stage` wrote (dist/artcraft). APPS: the seeded app ids, comma-separated (default: all 13).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
launcher=$(cd "$1" && pwd)
data=$(cd "$2/data/ps5proton/prefixes/artcraft/drive_c/ArtCraft/Launcher/ArtCraftLauncherData/data" && pwd)
apps=${3:-photocraft,vectorcraft,filmcraft,lightcraft,pdfcraft,effectcraft,designcraft,figcraft,wordcraft,soundcraft,deckcraft,cadcraft,gridcraft}
# crates/native has no tests folder of its own (v0.8.1): one made here goes again with the tests.
made=()
for folder in "$launcher/crates/native/tests" "$launcher/crates/ui-egui/tests"; do
    [ -d "$folder" ] || { mkdir "$folder"; made+=("$folder"); }
done
cp "$launcher/crates/ui-egui/Cargo.toml" "$launcher/crates/ui-egui/Cargo.toml.ps5-seed"
cp "$launcher/Cargo.lock" "$launcher/Cargo.lock.ps5-seed"
trap 'rm -f "$launcher/crates/native/tests/ps5_seed_manifest.rs" "$launcher/crates/ui-egui/tests/ps5_seed_settings.rs";
      for folder in ${made[@]+"${made[@]}"}; do rmdir "$folder"; done;
      mv "$launcher/crates/ui-egui/Cargo.toml.ps5-seed" "$launcher/crates/ui-egui/Cargo.toml";
      mv "$launcher/Cargo.lock.ps5-seed" "$launcher/Cargo.lock"' EXIT
cp "$here/ps5_seed_manifest.rs" "$launcher/crates/native/tests/ps5_seed_manifest.rs"
cp "$here/ps5_seed_settings.rs" "$launcher/crates/ui-egui/tests/ps5_seed_settings.rs"
# eframe stores with ron; the workspace already locks it, so this adds no new version.
sed -i 's/^\[dev-dependencies\]$/[dev-dependencies]\nron = "0.12"/' "$launcher/crates/ui-egui/Cargo.toml"
cd "$launcher"
PS5_SEED_DATA="$data" PS5_SEED_APPS="$apps" cargo test -p artcraft-launcher-native --test ps5_seed_manifest
PS5_SEED_DATA="$data" PS5_SEED_APPS="$apps" cargo test -p artcraft-launcher-ui-egui --test ps5_seed_settings
