#!/usr/bin/env bash
# Runs only inside the disposable Arch build container.
set -euo pipefail
pacman -Syu --noconfirm --needed base-devel git cmake ninja pkgconf boost robin-map \
    vulkan-headers vulkan-icd-loader glslang spirv-tools sdl3 ffmpeg fmt xxhash zydis \
    libx11 python python-pillow tk xdg-utils python-installer \
    xorg-server-xvfb xorg-xauth ttf-dejavu desktop-file-utils
useradd -m builder
install -d -o builder -g builder /build
mkdir -p /output
cp /repo/packaging/arch/{PKGBUILD,gow3,gow3.desktop} /build/
[[ $GOW3_COMMIT =~ ^[0-9a-f]{40}$ ]]
# Published recipes and SRCINFO must reproduce the exact release source, without CI env.
sed -i "s/^_commit=.*/_commit=$GOW3_COMMIT/" /build/PKGBUILD
chown -R builder:builder /build
# Git fetches only public source; credentials are never persisted in the container.
runuser -u builder -- env GOW3_COMMIT="$GOW3_COMMIT" GOW3_BUILD_JOBS=2 \
    bash -c 'cd /build && makepkg --cleanbuild --force --noconfirm'
cp /build/*.pkg.tar.zst /output/
cp /build/PKGBUILD /output/
runuser -u builder -- bash -c 'cd /build && makepkg --printsrcinfo' > /output/SRCINFO
# Install in a fresh environment in the separate smoke job before publication.
