#!/usr/bin/env bash
# Prints the commit a Syft Space image's changes are listed from, or nothing.
# That is the commit the previous :latest was built from, as read from the
# registry. If it is missing, or is the commit being built (a re-run after
# :latest moved), the newest entry in the changelog is used instead.
# Needs the repository's full history.
#
#   space_changes_start.sh <previous commit, may be empty> <commit being built>
set -uo pipefail

since="${1:-}"
commit="$2"

if [ -z "$since" ] || [ "$(git rev-parse "$since^{commit}" 2>/dev/null)" = "$(git rev-parse "$commit^{commit}")" ]; then
  since=$(grep -m1 -oP '^## Docker image \K\S+' packages/spaces/CHANGELOG.md || true)
fi
if [ -n "$since" ] && ! git rev-parse --verify --quiet "$since^{commit}" >/dev/null; then
  since=""
fi
echo "$since"
