#!/usr/bin/env bash
# Install or update the native Arch Linux package. Downloads never require root.
set -euo pipefail
repo=zamkara/Gow3Arch
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'Only x86_64 Linux is supported.' >&2; exit 1; }
for tool in pacman curl python3 sha256sum vercmp; do
    command -v "$tool" >/dev/null || { echo "Required command not found: $tool" >&2; exit 1; }
done
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
curl -fsSL --retry 3 "https://api.github.com/repos/$repo/releases/latest" -o "$work/release.json"
python3 - "$work" "$repo" <<'PY'
import json,pathlib,sys
work=pathlib.Path(sys.argv[1]);repo=sys.argv[2]
release=json.loads((work/'release.json').read_text())
assets=release.get('assets',[])
packages=[a for a in assets if a['name'].startswith('gow3-') and a['name'].endswith('-x86_64.pkg.tar.zst')]
if len(packages)!=1:raise SystemExit('Release must contain exactly one native gow3 package.')
package=packages[0]
checksums=next((a for a in assets if a['name']=='SHA256SUMS'),None)
if checksums is None:raise SystemExit('Release has no SHA256SUMS.')
for key,asset in [('package',package),('checksums',checksums)]:
    name=asset['name'];url=asset['browser_download_url']
    if pathlib.Path(name).name!=name or not url.startswith(f'https://github.com/{repo}/releases/download/'):
        raise SystemExit('Unexpected release asset location.')
    (work/(key+'.name')).write_text(name)
    (work/(key+'.url')).write_text(url)
PY
package=$(cat "$work/package.name")
curl -fsSL --retry 3 "$(cat "$work/package.url")" -o "$work/$package"
curl -fsSL --retry 3 "$(cat "$work/checksums.url")" -o "$work/SHA256SUMS"
python3 - "$work" "$package" <<'PY'
import pathlib,re,sys
work=pathlib.Path(sys.argv[1]);name=sys.argv[2]
lines=[line for line in (work/'SHA256SUMS').read_text().splitlines() if line[66:].lstrip('*')==name]
if len(lines)!=1 or not re.fullmatch(r'[a-f0-9]{64} [ *]'+re.escape(name),lines[0]):
    raise SystemExit('Missing or invalid package checksum.')
(work/'package.sha256').write_text(lines[0]+'\n')
PY
(cd "$work" && sha256sum --check package.sha256)
available=$(pacman -Qp "$work/$package" | awk '{print $2}')
installed=$(pacman -Q gow3 2>/dev/null | awk '{print $2}' || true)
if [[ -n $installed && $(vercmp "$installed" "$available") -ge 0 ]]; then
    echo "gow3 $installed is already current."
    exit 0
fi
if [[ $(id -u) == 0 ]]; then
    pacman -U -- "$work/$package" </dev/tty
else
    sudo pacman -U -- "$work/$package" </dev/tty
fi
echo "gow3 $available installed. Run: gow3"
