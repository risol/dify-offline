#!/usr/bin/env bash
set -euo pipefail

working_path="${PLUGIN_WORKING_PATH:-/app/storage/cwd}"
target_cache="${working_path}/.uv-cache"
mkdir -p "${target_cache}"

# The working directory is a persistent volume. Seed it idempotently from the
# image so upgrades can add cached wheels without needing network access.
if [ -d /opt/offline-uv-cache ]; then
  cp -a /opt/offline-uv-cache/. "${target_cache}/"
fi

export UV_OFFLINE=1
exec "$@"
