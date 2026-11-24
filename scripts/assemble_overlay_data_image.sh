#!/bin/sh
# Assemble a Zeratul image with the 8096K data partition and no config MTD.
set -eu

BASE=${1:?base image}
TAG=${2:?tag}
KERNEL=${3:?kernel}
ROOTFS=${4:?rootfs}
DATA=${5:?data jffs2}
OUT=${6:?output image}

python3 - "$BASE" "$TAG" "$KERNEL" "$ROOTFS" "$DATA" "$OUT" <<'PY'
import hashlib
import pathlib
import sys

base_p, tag_p, kernel_p, rootfs_p, data_p, out_p = map(pathlib.Path, sys.argv[1:])
base = base_p.read_bytes()
tag = tag_p.read_bytes()
kernel = kernel_p.read_bytes()
rootfs = rootfs_p.read_bytes()
data = data_p.read_bytes()

if len(base) != 16 * 1024 * 1024:
    raise SystemExit(f"base is not 16 MiB: {len(base)}")
if len(tag) > 352 * 1024:
    raise SystemExit(f"tag too large: {len(tag)}")
if len(kernel) > 2560 * 1024:
    raise SystemExit(f"kernel too large: {len(kernel)}")
if len(rootfs) > 5 * 1024 * 1024:
    raise SystemExit(f"rootfs too large: {len(rootfs)}")
if len(data) > 0x7E8000:
    raise SystemExit(f"data too large: {len(data)}")

img = bytearray(base)
img[0x040000:0x040000 + len(tag)] = tag
img[0x098000:0x098000 + len(kernel)] = kernel
img[0x318000:0x318000 + len(rootfs)] = rootfs
img[0x818000:0x818000 + len(data)] = data
out_p.write_bytes(img)
print(f"wrote {out_p} ({len(img)} bytes)")
print("sha256", hashlib.sha256(img).hexdigest())
PY
