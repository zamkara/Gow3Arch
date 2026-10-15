#!/usr/bin/env bash
# Clean Arch container: no compiler, source checkout, game dump or bundled GPU drivers.
set -euo pipefail
pacman -Syu --noconfirm --needed xorg-server-xvfb xorg-xauth ttf-dejavu
mapfile -t packages < <(printf '%s\n' /release/gow3-*-x86_64.pkg.tar.zst)
[[ ${#packages[@]} == 1 && -f ${packages[0]} ]]
# Official minimal Arch images omit documentation via NoExtract. Whitelist only
# this package's documentation, including its parent directory, inside this container.
# Later inverted patterns override earlier exclusions; retain hosts/resolv.conf exclusions.
printf '\n[options]\nNoExtract = !usr/share/doc/ !usr/share/doc/gow3/ !usr/share/doc/gow3/*\n' >> /etc/pacman.conf
pacman -U --noconfirm "${packages[0]}"
[[ -s /usr/share/doc/gow3/README.md ]]
for binary in /usr/lib/gow3/bin/gow3-probe /usr/lib/gow3/bin/gow3-gpu-capabilities /usr/lib/gow3/bin/gpu/libgow3gpu.so; do
    output=$(ldd "$binary")
    printf '%s\n' "$output"
    if grep -q 'not found' <<< "$output"; then exit 1; fi
done
# Private Python dependency is available without pip or PyInstaller.
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/lib/gow3/python python -c 'import iced_x86; from PIL import Image; import tkinter'
/usr/lib/gow3/bin/gow3-probe --cpu-features
useradd -m player
work=$(mktemp -d)
chown player:player "$work"
set +e
runuser -u player -- env HOME=/home/player XDG_DATA_HOME="$work/data" XDG_CONFIG_HOME="$work/config" \
    xvfb-run -a timeout 15 /usr/bin/gow3 > "$work/launcher.log" 2>&1
status=$?
set -e
cat "$work/launcher.log"
[[ $status == 124 ]] || { echo "Launcher exited unexpectedly: $status" >&2; exit 1; }
if grep -Eq 'Traceback|ImportError|ModuleNotFoundError' "$work/launcher.log"; then exit 1; fi
[[ -d $work/data/gow3 ]]
pacman -Qkk gow3
pacman -R --noconfirm gow3
[[ ! -e /usr/bin/gow3 && ! -e /usr/lib/gow3 ]]
[[ -d $work/data/gow3 ]] # Uninstall preserves user data.
echo 'PASS: native package installed, launcher stayed open as an unprivileged user, uninstall preserved data.'
