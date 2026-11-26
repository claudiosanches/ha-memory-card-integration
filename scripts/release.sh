#!/bin/sh
# Prepares a release on main: picks the version from the changelog, sets it in
# the manifest, dates the changelog section, then commits and tags. Pushing is
# left to you.
#
# The Unreleased entries pick the version: Removed bumps the major version
# (the minor before 1.0), Added, Changed or Deprecated the minor, and only
# Fixed or Security the patch. The first release is 0.1.0.
# Usage: scripts/release.sh [X.Y.Z]
set -eu
cd "$(dirname "$0")/.."

changelog=CHANGELOG.md
manifest=custom_components/memory_card/manifest.json
repo_url=https://github.com/claudiosanches/ha-memory-card-integration

fail() {
    echo "$*" >&2
    exit 1
}

[ -z "$(git status --porcelain)" ] || fail "Commit or stash your changes first."
[ "$(git branch --show-current)" = main ] || fail "Run it on main."

unreleased=$(awk '/^## \[Unreleased\]/ { found = 1; next } found && /^## / { exit } found { print }' "$changelog")
printf '%s\n' "$unreleased" | grep -q '^- ' || fail "$changelog has nothing under Unreleased."
types=$(printf '%s\n' "$unreleased" | sed -n 's/^### //p')
for type in $types; do
    case $type in
    Added | Changed | Deprecated | Removed | Fixed | Security) ;;
    *) fail "$changelog has an unknown section under Unreleased: $type" ;;
    esac
done

previous=$(sed -n 's/^## \[\([0-9][0-9.]*\)\] - .*/\1/p' "$changelog" | head -n 1)

if [ -n "${1:-}" ]; then
    version=$1
    printf '%s\n' "$version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || fail "VERSION takes X.Y.Z."
    if [ -n "$previous" ]; then
        newest=$(printf '%s\n%s\n' "$previous" "$version" | sort -V | tail -n 1)
        if [ "$version" = "$previous" ] || [ "$newest" != "$version" ]; then
            fail "$version is not after $previous."
        fi
    fi
elif [ -z "$previous" ]; then
    version=0.1.0
else
    case $types in
    *Removed*) bump="major" ;;
    *Added* | *Changed* | *Deprecated*) bump="minor" ;;
    *) bump="patch" ;;
    esac
    IFS=. read -r major minor patch <<EOF
$previous
EOF
    if [ "$bump" = major ] && [ "$major" = 0 ]; then
        bump="minor"
    fi
    case $bump in
    major) version=$((major + 1)).0.0 ;;
    minor) version=$major.$((minor + 1)).0 ;;
    patch) version=$major.$minor.$((patch + 1)) ;;
    esac
fi

! git rev-parse -q --verify "refs/tags/v$version" >/dev/null || fail "The tag v$version exists."

if [ -n "$previous" ]; then
    version_url="$repo_url/compare/v$previous...v$version"
else
    version_url="$repo_url/releases/tag/v$version"
fi
awk -v version="$version" -v date="$(date +%F)" -v repo="$repo_url" -v version_url="$version_url" '
    /^## \[Unreleased\]/ { print; print ""; print "## [" version "] - " date; next }
    /^\[Unreleased\]: / {
        print "[Unreleased]: " repo "/compare/v" version "...HEAD"
        print "[" version "]: " version_url
        linked = 1
        next
    }
    { print }
    END { if (!linked) { print ""; print "[Unreleased]: " repo "/compare/v" version "...HEAD"; print "[" version "]: " version_url } }
' "$changelog" >"$changelog.new"
mv "$changelog.new" "$changelog"

sed -i "s/^  \"version\": \".*\"\$/  \"version\": \"$version\"/" "$manifest"
./scripts/check-version.sh "$version"

git commit -q -am "chore: Release $version"
git tag -a "v$version" -m "Memory Card integration $version"

cat <<EOF
Tagged v$version. To publish it:

    git push origin main v$version

The release workflow runs the checks, then creates the GitHub release.
EOF
