#!/bin/sh
# Build a jzlzma rootfs container from a staging rootfs tree.
#
# Usage: build_rootfs_container.sh <rootfs-dir> <out.jzlzma> [lzma-tool]
#
# The container is [comp_size LE][0x27051956 LE][dict][orig][lzma stream],
# i.e. the 8-byte prefix plus the SDK lzma tool's jz_lzma_out.bin.
set -eu

ROOT=$1
OUT=$2
LZMA=${3:-/root/a1-work/sdk/kernel/kernel/scripts/ingenic_hardlzma/lzma}
WORK="${OUT}.work"

rm -rf "$WORK"
mkdir -p "$WORK"

( cd "$ROOT" && find . -print0 | cpio --null -o -H newc --quiet ) > "$WORK/rootfs.cpio"
( cd "$WORK" && "$LZMA" -z -k -f -1 rootfs.cpio )

python3 - "$WORK/jz_lzma_out.bin" "$OUT" <<'PY'
import struct
import sys

jz = open(sys.argv[1], "rb").read()
# magic must be little-endian: 0x27051956 -> 56 19 05 27
container = struct.pack("<I", len(jz)) + struct.pack("<I", 0x27051956) + jz
open(sys.argv[2], "wb").write(container)
print(f"container {len(container)} bytes (payload {len(jz)})")
PY

rm -rf "$WORK"
