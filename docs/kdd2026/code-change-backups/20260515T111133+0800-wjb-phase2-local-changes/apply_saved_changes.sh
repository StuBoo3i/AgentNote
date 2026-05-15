#!/usr/bin/env bash
set -euo pipefail
REPO=${1:-/nfsdat/home/jwangslm/DataAnalysis}
BACKUP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$REPO"
if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo "Refusing to apply: working tree is not clean. Commit/stash/clean current changes first." >&2
  exit 1
fi
if [ -s "$BACKUP_DIR/tracked_changes.patch" ]; then
  git apply --3way "$BACKUP_DIR/tracked_changes.patch"
fi
if [ -f "$BACKUP_DIR/untracked_files.tar.gz" ]; then
  tar -xzf "$BACKUP_DIR/untracked_files.tar.gz" -C "$REPO"
fi
echo "Applied saved changes from $BACKUP_DIR"
