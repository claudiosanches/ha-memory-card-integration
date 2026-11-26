#!/bin/sh
# Fails unless the manifest, pyproject.toml and the changelog have the given version.
# Usage: scripts/check-version.sh 0.1.0
set -eu
cd "$(dirname "$0")/.."

expected=$1
status=0

manifest=$(sed -n 's/^  "version": "\(.*\)"$/\1/p' custom_components/memory_card/manifest.json)
if [ "$manifest" != "$expected" ]; then
    echo "manifest.json has version '$manifest', expected '$expected'" >&2
    status=1
fi
pyproject=$(sed -n '/^\[project\]/,/^\[/s/^version = "\(.*\)"$/\1/p' pyproject.toml)
if [ "$pyproject" != "$expected" ]; then
    echo "pyproject.toml has version '$pyproject', expected '$expected'" >&2
    status=1
fi
version_pattern=$(printf '%s' "$expected" | sed 's/\./\\./g')
grep -Eq "^## \[$version_pattern\] - [0-9]{4}-[0-9]{2}-[0-9]{2}\$" CHANGELOG.md || {
    echo "CHANGELOG.md has no '## [$expected] - YYYY-MM-DD' section" >&2
    status=1
}

exit "$status"
