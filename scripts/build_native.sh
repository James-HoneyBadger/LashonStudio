#!/usr/bin/env bash
# Build the optional native PEG engine and copy it next to the Python package.
#
#   scripts/build_native.sh            # release build
#
# Requires a Rust toolchain (cargo) and a C linker. The resulting extension is
# optional: lashon works without it.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
crate="$root/crates/lashon-core"
target="$root/src/lashon/parser"

cargo build --release --manifest-path "$crate/Cargo.toml" --features python

so=""
for candidate in \
  "$root/target/release/liblashon_core.so" \
  "$crate/target/release/liblashon_core.so"; do
  if [[ -f "$candidate" ]]; then
    so="$candidate"
    break
  fi
done
if [[ -z "$so" ]]; then
  echo "error: build produced no shared library" >&2
  exit 1
fi
cp "$so" "$target/lashon_native.so"
echo "installed $(basename "$so") -> $target/lashon_native.so"
