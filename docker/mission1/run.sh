#!/usr/bin/env bash
# Build and test from Git Bash or POSIX bash; never mounts devices or USB.
set -euo pipefail
chunk="${1:-1}"
[[ "$chunk" =~ ^[0-9]+$ ]] || { echo "Chunk must be a nonnegative integer." >&2; exit 2; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mount_root="$root"
if command -v cygpath >/dev/null 2>&1; then mount_root="$(cygpath -m "$root")"; fi
cd "$root"
tag="amaze-mission1:chunk-$chunk"
build_args=()
if [[ "${NO_CACHE:-0}" == "1" ]]; then build_args+=(--no-cache); fi
docker build --platform linux/amd64 "${build_args[@]}" -f docker/mission1/Dockerfile -t "$tag" .
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' docker run --rm --platform linux/amd64 --network none \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$mount_root,dst=/workspace,readonly" --workdir /workspace \
  "$tag" python -m unittest discover -s tests/mission1 -v

