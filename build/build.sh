#!/usr/bin/env bash
# Build everything ArtCraft puts on a PS5, from pinned sources: the ArtCraft title (PPSA99278), its Wine runtime, and
# the ArtCraft desktop (ArtCraft Launcher, the apps, the session helper, the wallpaper).
#
#   build/build.sh [--jobs N]
#   build/build.sh --check       only what is quick: the toolchain, the sources at their pins with ArtCraft's patches,
#                                and every pinned download's URL and SHA-256 (the fork's tools/fetch-all.sh --check)
#   build/build.sh --until vulkan  stop once PS5_Vulkan's libc.prx and native tool are built (minutes; CI runs it)
#
# Run it in the build container (build/Dockerfile, README.md On the PC), or on an Arch Linux host with the
# packages that Dockerfile installs. WORK (default /work in the container, ~/artcraft-build elsewhere) holds the
# sibling checkouts the fork's build reads, its downloads and builds: tens of GB, and the first run takes hours (it
# builds Wine three times). Running it again resumes: each step skips what is already built.
#
# Result, in this checkout:
#   out/package/   the title folder and the runtime's pieces for a USB stick (the fork's tools/package-install.py),
#                  with README.txt; the title folder carries edition.json, so ArtCraft opens its own desktop
#   dist/artcraft/ the ArtCraft desktop, which `python3 -m artcraft_ps5 deploy` sends to the console
set -euo pipefail
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=${WORK:-$HOME/artcraft-build}
memory_gb=$(awk '/^MemTotal/ { print int($2 / 1048576) }' /proc/meminfo)
jobs=$(( $(nproc) < memory_gb / 2 ? $(nproc) : memory_gb / 2 ))   # a Wine compile job wants up to about 2 GB
(( jobs >= 1 )) || jobs=1
check=false
until=
while [ $# -gt 0 ]; do
    case $1 in
    --jobs) jobs=$2; shift ;;
    --check) check=true ;;
    --until) until=$2; shift; [[ $until == vulkan ]] || { echo "--until takes vulkan" >&2; exit 2; } ;;
    *) echo "usage: build/build.sh [--jobs N] [--check | --until vulkan]" >&2; exit 2 ;;
    esac
    shift
done
step() { printf '\n==> [%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
# Everything the build needs from this machine, checked before it starts, so a missing piece stops it in seconds with
# the whole list, not hours in. Beyond the tools the fork's README names, three parts are compiled for this machine
# against its own libraries, which the fork's owner's desktop happens to have: Proton Wine's amd_ags_x64 (libdrm),
# win32u (EGL) and winebus (SDL2), and Mesa's mesa_clc for RADV (the SPIR-V LLVM translator of this LLVM's
# major.minor, SPIRV-Tools, Clang's library). Every other part is built with a pinned cross toolchain. Two more tools
# run on this machine during the build: FFmpeg with x264 and AAC (tools/make-mf-video-clip.py makes the media probe's
# clip) and qrencode (ps5/tools/generate_assets.py draws the setup screen's QR code).
llvm=$(llvm-config --version 2>/dev/null || echo none)
[[ $llvm == 23.1.3 ]] || { echo "LLVM is $llvm; the pinned binaries need 23.1.3 (build/Dockerfile)" >&2; exit 2; }
IFS=. read -r llvm_major llvm_minor _ <<< "$llvm"
missing=()
for tool in git curl wget clang ld.lld python3 x86_64-w64-mingw32-gcc magick meson ninja cmake pkg-config cc \
    glslangValidator bison flex nasm m4 perl autoreconf patch rsync zip unzip sha256sum ffmpeg ffprobe qrencode \
    rsvg-convert; do
    command -v "$tool" > /dev/null || missing+=("$tool")
done
encoders=$(ffmpeg -hide_banner -encoders 2> /dev/null || true)   # read whole: grep -q would close the pipe early
for encoder in libx264 aac; do
    grep -qw "$encoder" <<< "$encoders" || missing+=("ffmpeg's $encoder encoder")
done
for module in libdrm libdrm_amdgpu sdl2 freetype2 gnutls zlib expat libudev 'SPIRV-Tools >= 2024.1'; do
    pkg-config --exists "$module" 2> /dev/null || missing+=("pkg-config: $module")
done
pkg-config --exists "LLVMSPIRVLib >= $llvm_major.$llvm_minor" "LLVMSPIRVLib < $llvm_major.$((llvm_minor + 1))" \
    2> /dev/null || missing+=("pkg-config: LLVMSPIRVLib $llvm_major.$llvm_minor.x (the SPIR-V LLVM translator of this LLVM)")
printf '#include <EGL/egl.h>\nint main(void) { return !eglGetProcAddress("eglInitialize"); }\n' |
    cc -x c - -lEGL -o /dev/null 2> /dev/null || missing+=("EGL (EGL/egl.h, -lEGL)")
[[ -e $(llvm-config --libdir)/libclang-cpp.so ]] || missing+=("libclang-cpp.so beside LLVM")
for module in PIL numpy fontTools pefile mako markupsafe yaml packaging cryptography; do
    python3 -c "import $module" 2> /dev/null || missing+=("python: $module")
done
if (( ${#missing[@]} )); then
    printf 'missing: %s\n' "${missing[@]}" >&2
    echo "run this in the build container (build/Dockerfile), or install the above" >&2
    exit 2
fi
mkdir -p "$work"
cd "$work"

# clone NAME URL: a plain clone of each default branch; the fork's build reads them at its own pins (git archive).
clone() {
    local try
    for try in 1 2 3 4 5; do   # a dropped connection is tried again; a half-made clone is cleared first
        if [[ -d $1/.git ]]; then git -C "$1" fetch -q origin && return; else git clone -q "$2" "$1" && return; rm -rf "$1"; fi
        (( try < 5 )) || return 1
        echo "git: $1, try $try failed; again in $((try * 15)) s" >&2
        sleep $((try * 15))
    done
}

step "sources beside the fork, in $work (the fork's README, Set up the console, step 0)"
clone PS5_Vulkan https://github.com/mihawk-99/PS5_Vulkan.git
clone PS5_Mesa https://github.com/mihawk-99/PS5_Mesa.git
clone PS5_PayloadSDK https://github.com/mihawk-99/PS5_PayloadSDK.git
clone PS5-Lapy-JB-Daemon https://github.com/mpereiraesaa/PS5-Lapy-JB-Daemon.git

step "the Mihawk OS fork at its pin, with ArtCraft's patches (branch artcraft)"
(cd "$src" && python3 -m artcraft_ps5 mihawk prepare --dir "$work/PS5_MihawkOS")
fork=$work/PS5_MihawkOS
title=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["titleId"])' "$fork/ps5/sce_sys/param.json")

if $check; then
    step "every pinned input of the fork's build: URL and SHA-256 (tools/fetch-all.sh --check)"
    status=0
    (cd "$fork" && bash tools/fetch-all.sh --check) || status=$?
    # 0: all there; 2: something still to fetch, as on a first run; 1: a pin is broken.
    (( status != 1 )) || { echo "a pinned input of the fork's build is broken" >&2; exit 1; }
    echo "the build environment and the sources are ready (title $title)"
    exit 0
fi

step "PS5_Vulkan at the fork's pin: its payload SDK, runtime/libc.prx and the native tool"
vulkan_pin=$(sed -n 's/^revision=//p' "$fork/tools/setup-graphics-foundation.sh" | head -1)
git -C PS5_Vulkan checkout -q "$vulkan_pin"
if [[ ! -f PS5_Vulkan/runtime/libc.prx || ! -x PS5_Vulkan/build/host/ps5-native-tool ]]; then
    (cd PS5_Vulkan && bash tools/setup-native-dependencies.sh)
    # Its make goes on to a demo app MihawkOS does not use and stops there (the fork's README): what counts is these two.
    make -C PS5_Vulkan -j"$jobs" || true
fi
[[ -f PS5_Vulkan/runtime/libc.prx && -x PS5_Vulkan/build/host/ps5-native-tool ]] ||
    { echo "PS5_Vulkan did not build runtime/libc.prx and build/host/ps5-native-tool" >&2; exit 1; }
if [[ $until == vulkan ]]; then
    ls -l PS5_Vulkan/runtime/libc.prx PS5_Vulkan/build/host/ps5-native-tool
    exit 0
fi

step "the fork's pinned one-time inputs (tools/fetch-all.sh; the host Wine build takes hours)"
(cd "$fork" && JOBS=$jobs bash tools/fetch-all.sh)

step "the title and its runtime (tools/build-production.sh; two more Wine builds)"
(cd "$fork" && bash tools/build-production.sh --jobs "$jobs")

step "the ArtCraft desktop: the session helper, the launcher and the apps (dist/artcraft)"
make -C "$src/session"
(cd "$src" && python3 -m artcraft_ps5 fetch && python3 -m artcraft_ps5 wallpaper && python3 -m artcraft_ps5 stage --clean)
# The title reads edition.json from its own folder: in the title it opens ArtCraft's desktop from the first start,
# once deploy has sent that desktop (until then it shows its library).
cp "$src/dist/artcraft/data/homebrew/$title/edition.json" "$fork/dist/$title/edition.json"

step "the install package (out/package)"
rm -rf "$src/out/package"
(cd "$fork" && python3 tools/package-install.py --out "$src/out/package")

cat <<EOF

ArtCraft is built.
  $src/out/package   copy to the console as its README.txt says: the title folder $title into /data/homebrew,
                     usb/ to a USB stick; open ArtCraft and its setup installs the runtime from the stick
  $src/dist/artcraft then send the desktop: python3 -m artcraft_ps5 deploy (PS5_HOST=<console address>)
EOF
