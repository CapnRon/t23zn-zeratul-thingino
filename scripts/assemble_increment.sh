#!/bin/sh
# Replace the 6 MiB rootfs slot of a 16 MiB ZRT image.
#
# Usage: assemble_increment.sh <base-image> <rootfs.jzlzma> <out.bin>
#
# Base image supplies boot/tag/kernel/recovery/system; the rootfs slot is
# padded with 0xFF and the jzlzma container is inserted at 0x318000.
set -eu

BASE=$1
ROOTFS=$2
OUT=$3

python3 - "$BASE" "$ROOTFS" "$OUT" <<'PY'
import sys

base = bytearray(open(sys.argv[1], "rb").read())
rootfs = open(sys.argv[2], "rb").read()

if len(base) != 16 * 1024 * 1024:
    sys.exit("base image must be 16 MiB")
if len(rootfs) > 6 * 1024 * 1024:
    sys.exit("rootfs container must fit the 6 MiB rootfs slot")

base[0x318000:0x918000] = b"\xff" * (0x918000 - 0x318000)
base[0x318000:0x318000 + len(rootfs)] = rootfs
open(sys.argv[3], "wb").write(base)
print(f"wrote {sys.argv[3]} ({len(base)} bytes), rootfs {len(rootfs)} bytes")
PY
