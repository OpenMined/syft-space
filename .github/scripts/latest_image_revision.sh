#!/usr/bin/env bash
# Prints the commit the image's :latest tag was built from, or nothing.
# The commit is an annotation on the multi-arch index, or on older images a
# label in the per-arch image config.
#
#   latest_image_revision.sh ghcr.io/openmined/syft-space
set -uo pipefail

image="$1"
key="org.opencontainers.image.revision"

find_revision() {
  jq -r --arg key "$key" \
    '[.. | objects | select(has($key)) | .[$key]] | first // empty'
}

revision=$(docker buildx imagetools inspect --raw "${image}:latest" 2>/dev/null | find_revision || true)
if [ -z "$revision" ]; then
  revision=$(docker buildx imagetools inspect "${image}:latest" --format '{{json .Image}}' 2>/dev/null | find_revision || true)
fi
echo "$revision"
