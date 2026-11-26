#!/bin/sh
# Prints the changelog entries of a released version, for its GitHub release.
# Usage: scripts/release-notes.sh 0.1.0
set -eu
cd "$(dirname "$0")/.."

notes=$(awk -v heading="## [$1] - " '
    index($0, heading) == 1 { found = 1; next }
    found && /^## / { exit }
    found && !/^\[(Unreleased|[0-9]+\.[0-9]+\.[0-9]+)\]: / { print }
' CHANGELOG.md | sed '/./,$!d')

if [ -z "$notes" ]; then
    echo "CHANGELOG.md has no entries for $1" >&2
    exit 1
fi
printf '%s\n' "$notes"
