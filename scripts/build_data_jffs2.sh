#!/bin/sh
# Build the Zeratul data-partition JFFS2 image.
set -eu

SRC=${1:-data-overlay}
OUT=${2:-out/data.jffs2}
SIZE=${3:-0x7e8000}

command -v mkfs.jffs2 >/dev/null || {
	echo "mkfs.jffs2 not found (install mtd-utils)" >&2
	exit 1
}

[ -d "$SRC" ] || {
	echo "data root not found: $SRC" >&2
	exit 1
}

mkdir -p "$(dirname "$OUT")"
mkfs.jffs2 -r "$SRC" -o "$OUT" -e 0x8000

python3 - "$OUT" "$SIZE" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
size = int(sys.argv[2], 0)
b = p.read_bytes()
if len(b) > size:
    raise SystemExit(f"data image too large: {len(b)} > {size}")
p.write_bytes(b + b"\xff" * (size - len(b)))
print(f"data image: {p} ({size} bytes)")
PY
