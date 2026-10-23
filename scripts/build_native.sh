#!/usr/bin/env bash
# Build the optional native PEG engine and copy it next to the Python package.
#
#   scripts/build_native.sh            # release build
#
# Requires a Rust toolchain (cargo) and a C linker. The resulting extension is
# optional: parsercraft works without it.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
crate="$root/crates/parsercraft-core"
target="$root/src/parsercraft/parser"

cargo build --release --manifest-path "$crate/Cargo.toml" --features python

so="$(find "$root/target/release" "$crate/target/release" -maxdepth 1 -name 'libparsercraft_core*.so' 2>/dev/null | head -1)"
if [[ -z "$so" ]]; then
  echo "error: build produced no shared library" >&2
  exit 1
fi
cp "$so" "$target/parsercraft_native.so"
echo "installed $(basename "$so") -> $target/parsercraft_native.so"
