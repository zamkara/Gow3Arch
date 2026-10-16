# Gow3Arch

Native Arch Linux packaging of God of War III Remastered's PC runtime and launcher.
Omarchy uses the same pacman package. This fork publishes `.pkg.tar.zst` packages;
Windows and AppImage releases remain the responsibility of
[the upstream project](https://github.com/FelipePrado0/gow3_pc).

## Install and update

Run the same command for a first installation and subsequent updates:

```bash
curl -fsSL https://github.com/zamkara/Gow3Arch/releases/latest/download/install.sh | bash
```

The script requires Arch Linux x86_64, curl and Python. It downloads the latest
published package, verifies SHA-256 against the same release, compares versions
with pacman's `vercmp`, and skips an installed version that is already current or
newer. Downloads do not require root; only the pacman transaction uses sudo.
Authentication and confirmation read from the terminal, including when piped to
bash. Checksums detect corruption; release authenticity relies on GitHub HTTPS
and this repository's access controls, not an independent package signature.

Alternatively download the package and `SHA256SUMS` from
[Releases](https://github.com/zamkara/Gow3Arch/releases/latest), verify the package's
checksum, and install it with `sudo pacman -U ./gow3-*.pkg.tar.zst`.
This repository is not a pacman sync repository: use the command above for updates.
Do not partially upgrade an Arch installation; keep your system repositories current.

## Run

Open **Launcher God of War III Remastered** in your application menu or run `gow3`.
Choose your game dump, save your settings and press Play. `gow3 --play` uses saved
settings. The separate **God of War III Remastered** application entry runs
`gow3 --play` and reads the same saved launcher configuration on every launch.
The launcher entry also offers a Play action. Steam shortcuts use the
native wrapper so the writable paths and private Python dependency are preserved.

You need an x86_64 CPU with AVX, a Vulkan 1.3 capable GPU and its driver, and your
own PS4 game dump. No game files, firmware, proprietary FSR models, GPU drivers,
Wine, AppImage runtime or frozen Python interpreter are shipped. Upstream supports
CUSA01623 and CUSA01715, versions 01.00 and 01.02; this fork's CI checks packaging
and launcher startup, not gameplay or every GPU/Wayland setup.

Pacman manages system libraries, Python, Tk and Pillow. The checksum-pinned
iced-x86 ABI3 module is installed privately under `/usr/lib/gow3/python` because
it is not in the official Arch repositories. It never replaces system Python
packages. Build tools are not needed to play. Vulkan drivers remain host-managed.

The performance overlay defaults to a one-second refresh interval. Change
**Graphics → Overlay update interval** in the launcher or **Overlay → Appearance →
Update interval** in the in-game menu to 1, 2, 5 or 10 seconds. Both use the same
`overlay_interval_ms` key in `gow3.ini`; this affects displayed readings, not FPS.

The launcher shows `Arch <commit>` beside its version for native packages. Compare
that build identity after an update; an already running launcher or game must be
restarted to load updated Python code and GPU libraries. The experimental pipeline
binary cache is disabled by default; enabling it is an explicit A/B test and may
trigger driver failures. Existing saved preferences are preserved on upgrades.

## User files and removal

- Game settings, saves, prepared files, mods and caches: `${XDG_DATA_HOME:-~/.local/share}/gow3`.
- Launcher settings: `${XDG_CONFIG_HOME:-~/.config}/gow3-launcher`.
- `GOW3_DATA_DIR` overrides the game data directory.
- Program files: `/usr/lib/gow3`; command: `/usr/bin/gow3`.

Remove the package with `sudo pacman -Rns gow3`. Your saves and configuration remain
in your home directory. Remove those two data directories separately only if you
want to erase your own data. Launcher's self-installers for Windows/AppImage are
not used by the native package.

## Build and release

```bash
git clone https://github.com/zamkara/Gow3Arch.git
cd Gow3Arch/packaging/arch
GOW3_COMMIT=$(git rev-parse HEAD) makepkg -s
```

The recipe pins the complete source commit, follows its pinned submodules and
verifies downloaded VMA and iced-x86 assets. `GOW3_COMMIT` must be a full commit
hash. The default recipe revision is a known source checkpoint; the command above
builds your current checkout revision. Runtime binaries are compiled for generic
x86_64 without host-specific CPU tuning. LTO and PGO are disabled for predictable
CI resource use; build concurrency defaults to two jobs.

The GitHub workflow builds in a disposable Arch container as an unprivileged
user, runs regression tests, then installs the resulting package in a fresh Arch
container and opens the launcher as an unprivileged user on Xvfb. It checks shared
libraries and clean package removal before publishing. Pushes to main and manual
runs publish a complete release tagged with the source commit hash; pull requests
only build and test. Failed builds do not publish a release. Only native Arch
artifacts are produced. Every main-branch run fetches and merges upstream before building, including a daily
run at 03:43 Asia/Jakarta. Upstream source history is retained through a three-way
merge. The fork's `.github/`, `packaging/`, root READMEs, upstream documentation
snapshot and packaging regression tests are restored from the fork after merging.
Upstream Windows/AppImage workflows cannot replace or reappear beside the native
workflow. Runtime, renderer, launcher, source submodules and game patches continue
to receive upstream fixes while cleanly merged local source changes are preserved.

A source conflict aborts the merge without pushing changes or publishing a release;
it needs review. A successful merge is pushed back to this repository, and every
subsequent build, test and release uses that exact resulting commit. GitHub's own
workflow token prevents the synchronization push from triggering a recursive run.
A source commit that already has a published native release skips the expensive
build and release stages. Automatic synchronization reduces routine maintenance; it cannot guarantee that
upstream changes will remain compatible with Arch or our local changes.

See [upstream documentation](docs/UPSTREAM.md) for runtime behavior, controls,
known limitations and development details. Its Windows/AppImage instructions refer
to upstream releases, not Gow3Arch. Translated upstream READMEs are retained as
historical upstream documentation.

## Credits

This fork builds on [Felipe Prado's gow3_pc](https://github.com/FelipePrado0/gow3_pc),
which builds on Supermedo's Windows port and deadinside28's original:

- **deadinside28**: [bloodborne_pc](https://github.com/deadinside28/bloodborne_pc), the original
  native port.
- **Supermedo** (Mohammed Albarghouthi): [bloodborne_pc for Windows](https://github.com/Supermedo/bloodborne_pc),
  the fork this project comes from.
- **cuesta4**: [shadPS4 fork focused on God of War III Remastered](https://github.com/cuesta4/shadPS4/tree/eltutz)
  (branch `eltutz`). The game's rendering in this port depends on its fixes: the GNM blend
  rewrite, depth/stencil state and image aliasing. cuesta4 is also a co-author of the
  resolution, texture fix, 120 FPS and skip videos patches (below). If you play on shadPS4,
  this is the build to use for God of War III.
- **shadPS4 team**: the [shadPS4](https://github.com/shadps4-emu/shadPS4) video core, which does
  all the GPU and shader translation to Vulkan in this port.

Patches: kvicken and cuesta4 (resolution, texture fix, 120 FPS and skip videos, building on the
PS3 patches by illusion0001), published for shadPS4 in
[shadps4-emu/ps4_cheats#145](https://github.com/shadps4-emu/ps4_cheats/pull/145) and adapted to
this executable. The 240 FPS patch was adapted by Felipe Prado from the 120 FPS patch.
Cheats: adapted from Celogamez's [GoldHEN cheats](https://github.com/GoldHEN/GoldHEN_Cheat_Repository).

Also used: [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9), [FFmpeg](https://ffmpeg.org),
[SDL3](https://github.com/libsdl-org/SDL), [Dear ImGui](https://github.com/ocornut/imgui),
[sirit](https://github.com/shadps4-emu/sirit), [magic_enum](https://github.com/Neargye/magic_enum),
[miniz](https://github.com/richgel999/miniz), [xbyak](https://github.com/herumi/xbyak),
[Vulkan Memory Allocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator),
[FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan) and the AMD FidelityFX SDK,
[MSYS2](https://www.msys2.org), [LLVM](https://llvm.org) and [Pillow](https://python-pillow.org).

## License

GNU GPL v2 or later ([LICENSE](https://github.com/FelipePrado0/gow3_pc/blob/main/LICENSE)). Third-party components keep their own licenses.
