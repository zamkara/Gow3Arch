#!/usr/bin/env bash
# Merge upstream source without replacing this fork's distribution policy.
set -euo pipefail
upstream_url=${1:-https://github.com/FelipePrado0/gow3_pc.git}
upstream_branch=${2:-main}
[[ -z $(git status --porcelain) ]] || { echo 'Upstream sync requires a clean checkout.' >&2; exit 1; }
git fetch --no-tags "$upstream_url" "$upstream_branch"
upstream_commit=$(git rev-parse FETCH_HEAD)
if git merge-base --is-ancestor "$upstream_commit" HEAD; then
    echo 'Upstream is already synchronized.'
    exit 0
fi
# Save this fork's protected tree from before the merge, including upstream additions/deletions.
protected=(.github packaging README.md README.es.md README.pt-BR.md docs/UPSTREAM.md tests/test_arch_packaging.py)
original=$(git rev-parse HEAD)
merge_status=0
git merge --no-ff --no-commit "$upstream_commit" || merge_status=$?
if (( merge_status > 1 )); then
    git merge --abort || true
    exit "$merge_status"
fi
git restore --source="$original" --staged --worktree -- "${protected[@]}"
if [[ -n $(git ls-files --unmerged) ]]; then
    echo 'Source conflicts require review; no upstream changes will be pushed.' >&2
    git diff --name-only --diff-filter=U >&2
    git merge --abort
    exit 1
fi
# Source history is retained even when all upstream changes were in protected files.
git commit -m "Merge upstream ${upstream_commit:0:12} while preserving native Arch distribution"
echo "Synchronized upstream $upstream_commit"
