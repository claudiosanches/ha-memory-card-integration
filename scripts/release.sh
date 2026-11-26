#!/bin/sh
# Prepares a release on main: picks the version from the changelog, sets it in
# the manifest and pyproject.toml, dates the changelog section, then commits
# and tags. Pushing is left to you.
#
# The Unreleased entries pick the version: Removed bumps the major version
# (the minor before 1.0), Added, Changed or Deprecated the minor, and only
# Fixed or Security the patch. The first release is 0.1.0.
# Usage: scripts/release.sh [X.Y.Z]
set -eu
cd "$(dirname "$0")/.."

branch=main
changelog=CHANGELOG.md
repo_url=https://github.com/claudiosanches/ha-memory-card-integration
# X.Y.Z without leading zeros.
semver='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'

fail() {
    echo "$*" >&2
    exit 1
}

# Runs a sed script on a file in place, without GNU sed's -i.
edit() {
    sed "$2" "$1" >"$1.new"
    mv "$1.new" "$1"
}

[ "$#" -le 1 ] || fail "Usage: scripts/release.sh [X.Y.Z]"
[ -z "$(git status --porcelain)" ] || fail "Commit or stash your changes first."
[ "$(git branch --show-current)" = "$branch" ] || fail "Run it on $branch."
if git rev-parse -q --verify "refs/remotes/origin/$branch" >/dev/null; then
    git fetch -q origin "$branch"
    git merge-base --is-ancestor "origin/$branch" HEAD || fail "$branch is behind origin/$branch. Pull first."
fi

# The Unreleased sections that have entries, one per line.
types=$(awk '
    /^## \[Unreleased\]/ { found = 1; next }
    !found { next }
    /^## / { exit }
    /^### / {
        heading = substr($0, 5)
        if (heading !~ /^(Added|Changed|Deprecated|Removed|Fixed|Security)$/) {
            print "Unknown section under Unreleased: " $0 > "/dev/stderr"
            failed = 1
            exit
        }
        next
    }
    /^- / {
        if (heading == "") {
            print "An Unreleased entry is outside a section: " $0 > "/dev/stderr"
            failed = 1
            exit
        }
        if (!(heading in used)) print heading
        used[heading] = 1
    }
    END { exit failed }
' "$changelog") || fail "Fix the Unreleased section of $changelog."
[ -n "$types" ] || fail "$changelog has nothing under Unreleased."

previous=$(sed -n 's/^## \[\([^]]*\)\] - .*/\1/p' "$changelog" | grep -v '^Unreleased$' | head -n 1 || true)
if [ -n "$previous" ]; then
    printf '%s\n' "$previous" | grep -Eq "$semver" || fail "$changelog has a malformed version: $previous"
fi

if [ -n "${1:-}" ]; then
    version=$1
    printf '%s\n' "$version" | grep -Eq "$semver" || fail "VERSION takes X.Y.Z, without leading zeros."
    if [ -n "$previous" ] && ! awk -v a="$version" -v b="$previous" 'BEGIN {
        split(a, x, "."); split(b, y, ".")
        for (i = 1; i <= 3; i++) if (x[i] != y[i]) exit !(x[i] + 0 > y[i] + 0)
        exit 1
    }'; then
        fail "$version is not after $previous."
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
    if [ "$bump" = major ] && [ "$major" -eq 0 ]; then
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
awk -v version="$version" -v date="$(date +%F)" -v repo="$repo_url" -v branch="$branch" -v version_url="$version_url" '
    /^## \[Unreleased\]/ { print; print ""; print "## [" version "] - " date; next }
    /^\[Unreleased\]: / {
        print "[Unreleased]: " repo "/compare/v" version "..." branch
        print "[" version "]: " version_url
        linked = 1
        next
    }
    { print }
    END { if (!linked) { print ""; print "[Unreleased]: " repo "/compare/v" version "..." branch; print "[" version "]: " version_url } }
' "$changelog" >"$changelog.new"
mv "$changelog.new" "$changelog"

edit custom_components/memory_card/manifest.json "s/^  \"version\": \".*\"\$/  \"version\": \"$version\"/"
edit pyproject.toml "/^\[project\]/,/^\[/ s/^version = \".*\"\$/version = \"$version\"/"
./scripts/check-version.sh "$version"

git commit -q -am "chore: Release $version"
git tag -a "v$version" -m "Memory Card integration $version"

cat <<EOF
Tagged v$version. To publish it, push both at once:

    git push --atomic origin $branch v$version

The release workflow runs the checks, then creates the GitHub release.
EOF
