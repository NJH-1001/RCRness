#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "$0")" && pwd)"
rom="${1:?Usage: ./build.sh /path/to/owned-ROM.nes}"
rom="$(cd -- "$(dirname -- "$rom")" && pwd)/$(basename -- "$rom")"
if command -v sha256sum >/dev/null; then
    actual="$(sha256sum "$rom" | cut -d ' ' -f 1)"
else
    actual="$(shasum -a 256 "$rom" | cut -d ' ' -f 1)"
fi
if [[ "$actual" != b95f8def04c0012604b7cc68cf4ed8f49b2dfe4beda6182051de4b2423bea7b1 ]]; then
    echo 'Unsupported ROM: select the exact USA revision documented in README.md.' >&2
    exit 1
fi
for tool in git cmake ninja cc; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
engine="$root/nesrecomp"
pin="$(tr -d '\r\n' < "$root/NESRECOMP_COMMIT")"
if [[ ! -f "$engine/recompiler/CMakeLists.txt" ]]; then
    git clone https://github.com/NJH-1001/nesrecomp.git "$engine"
    git -C "$engine" checkout --detach "$pin"
fi
[[ "$(git -C "$engine" rev-parse HEAD)" == "$pin" ]] || { echo 'Engine revision differs from the release pin.' >&2; exit 1; }
patch="$root/engine-patches/adaptive-renderer.patch"
if ! git -C "$engine" apply --reverse --check "$patch" 2>/dev/null; then
    git -C "$engine" apply --check "$patch"
    git -C "$engine" apply "$patch"
fi
cmake -S "$engine/recompiler" -B "$root/build-public/recompiler" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$root/build-public/recompiler" --parallel 2
(cd "$root" && "$root/build-public/recompiler/NESRecomp" "$rom" --game "$root/game.toml")
cmake -S "$root" -B "$root/build-public" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DNESRECOMP_ENABLE_TRACE=OFF -DNESRECOMP_ENABLE_STACK_TRACKING=OFF \
    -DNESRECOMP_ENABLE_POSTMORTEM_RINGS=OFF
cmake --build "$root/build-public" --parallel 2
printf 'Built %s\n' "$root/build-public/RCRness"
