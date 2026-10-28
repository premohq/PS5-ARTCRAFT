# The ArtCraft build environment, at fixed versions: the host tools Mihawk OS's README lists, on Arch Linux as its owner
# builds, with clang/LLD/LLVM 23.1.3 as Arch packages them (the build that reproduces the fork's pinned root-access
# daemon byte for byte, .github/workflows/daemon.yml) and MinGW for ArtCraft's session helper.
#
#   docker build -t artcraft-build build
#   docker run --rm -it -v artcraft-work:/work -v "$PWD":/src artcraft-build
#
# The second command runs build/build.sh: the sibling sources, downloads and builds (tens of GB) stay in the
# artcraft-work volume, and what goes on the console lands in out/ of this checkout (README.md, On the PC).
FROM archlinux:base-devel
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Arch Linux's packages as they were on one day (the Arch Linux Archive), so a later build installs the same ones.
ARG ARCH_SNAPSHOT=2026/10/27
RUN echo "Server = https://archive.archlinux.org/repos/${ARCH_SNAPSHOT}/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist \
 && pacman -Syyuu --noconfirm \
 && pacman -S --noconfirm --needed \
      git curl wget unzip zip xz zstd patch make cmake ninja meson pkgconf autoconf automake libtool bison flex perl \
      gettext nasm glslang spirv-tools zlib freetype2 gnutls libunwind vulkan-headers \
      python python-pillow python-pefile python-fonttools python-numpy python-mako python-markupsafe python-yaml \
      python-packaging python-cryptography python-pytest \
      imagemagick librsvg cairo pango fontconfig \
      mingw-w64-gcc rsync which file jq

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
 && pacman -U --noconfirm "${urls[@]}" \
 && sed -i 's/^#IgnorePkg *=.*/IgnorePkg = llvm-libs llvm clang-libs clang lld compiler-rt/' /etc/pacman.conf \
 && pacman -Scc --noconfirm \
 && clang --version | head -1 | grep -qx "clang version $LLVM_VERSION" \
 && ld.lld --version | grep -q "^LLD $LLVM_VERSION"

# Git refuses a checkout another user owns; the sources come in through volumes.
RUN git config --system safe.directory '*' \
 && git config --system user.name 'ArtCraft build' \
 && git config --system user.email 'build@artcraft.invalid'

ENV WORK=/work
WORKDIR /src
CMD ["bash", "/src/build/build.sh"]
