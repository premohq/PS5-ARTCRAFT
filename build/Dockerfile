# The ArtCraft build environment, at fixed versions: the host tools Mihawk OS's README lists, on Arch Linux as its owner
# builds, with clang/LLD/LLVM 23.1.3 as Arch packages them (the build that reproduces the fork's pinned root-access
# daemon byte for byte, .github/workflows/daemon.yml) and MinGW for ArtCraft's session helper. libdrm, libglvnd (EGL),
# SDL2 and the SPIR-V LLVM translator are for the parts built for this machine itself: Proton Wine's amd_ags_x64,
# win32u and winebus, and Mesa's mesa_clc for RADV. FFmpeg (with x264 and AAC) and qrencode make the media probe's
# clip and the setup screen's QR code. build/build.sh checks all of it before it starts.
#
# Every download in the container is retried (net-retry/): curl and wget through their configuration files, Python's
# urllib through sitecustomize, pacman in a loop. A build fetches its pinned inputs over hours, once each; one dropped
# connection should not lose it.
#
#   docker build -t artcraft-build build
#   docker run --rm -it -v artcraft-work:/work -v "$PWD":/src artcraft-build
#
# The second command runs build/build.sh: the sibling sources, downloads and builds (tens of GB) stay in the
# artcraft-work volume, and what goes on the console lands in out/ of this checkout (README.md, On the PC).
FROM archlinux:base-devel
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY net-retry/curlrc /root/.curlrc

# Arch Linux's packages as they were on one day (the Arch Linux Archive), so a later build installs the same ones.
ARG ARCH_SNAPSHOT=2026/10/27
RUN echo "Server = https://archive.archlinux.org/repos/${ARCH_SNAPSHOT}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist \
 && for try in 1 2 3 4 5; do \
      pacman -Syyuu --noconfirm && pacman -S --noconfirm --needed \
        git curl wget unzip zip xz zstd patch make cmake ninja meson pkgconf autoconf automake libtool bison flex perl \
        gettext nasm glslang spirv-tools zlib freetype2 gnutls libunwind vulkan-headers libdrm libglvnd sdl2 \
        spirv-llvm-translator ffmpeg qrencode \
        python python-pillow python-pefile python-fonttools python-numpy python-mako python-markupsafe python-yaml \
        python-packaging python-cryptography python-pytest \
        imagemagick librsvg cairo pango fontconfig \
        mingw-w64-gcc rsync which file jq \
      && break; \
      (( try < 5 )) || exit 1; echo "pacman: try $try failed; again in $((try * 20)) s" >&2; sleep $((try * 20)); \
    done

# clang, LLD and LLVM 23.1.3 exactly, from the Arch Linux Archive, held there: the fork's pinned binaries are made with
# that release, and Arch's build of it (not LLVM's own, which names its git revision in every binary's .comment).
ARG LLVM_VERSION=23.1.3
RUN archive=https://archive.archlinux.org/packages \
 && urls=() \
 && for name in llvm-libs llvm clang-libs clang lld compiler-rt; do \
      file=$(curl -sSf "$archive/${name:0:1}/$name/" | grep -o "\"$name-$LLVM_VERSION-[0-9]*-x86_64.pkg.tar.zst\"" | \
        tr -d '"' | sort -V | tail -1) \
      && test -n "$file" && urls+=("$archive/${name:0:1}/$name/$file"); \
    done \
 && test ${#urls[@]} -eq 6 \
 && for try in 1 2 3 4 5; do \
      pacman -U --noconfirm "${urls[@]}" && break; \
      (( try < 5 )) || exit 1; echo "pacman: try $try failed; again in $((try * 20)) s" >&2; sleep $((try * 20)); \
    done \
 && sed -i 's/^#IgnorePkg *=.*/IgnorePkg = llvm-libs llvm clang-libs clang lld compiler-rt/' /etc/pacman.conf \
 && pacman -Scc --noconfirm \
 && clang --version | head -1 | grep -qx "clang version $LLVM_VERSION" \
 && ld.lld --version | grep -q "^LLD $LLVM_VERSION"

# wget's configuration once wget owns /etc/wgetrc, and urllib's retries in every Python.
COPY net-retry/wgetrc /etc/wgetrc
COPY net-retry/sitecustomize.py /tmp/sitecustomize.py
RUN mv /tmp/sitecustomize.py "$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/" \
 && python3 -c 'import urllib.request, sitecustomize; assert urllib.request.urlopen is sitecustomize.urlopen'

# Git refuses a checkout another user owns; the sources come in through volumes.
RUN git config --system safe.directory '*' \
 && git config --system user.name 'ArtCraft build' \
 && git config --system user.email 'build@artcraft.invalid'

ENV WORK=/work
WORKDIR /src
CMD ["bash", "/src/build/build.sh"]
