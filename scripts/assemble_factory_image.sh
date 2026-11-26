#!/bin/sh
# Assemble a 16 MiB factory-layout ZRT image.
#
#   assemble_factory_image.sh BASE TAG KERNEL ROOTFS OUT
#
# BASE   16 MiB image providing SPL + recovery/common/system/config
#        (the pinned artifacts/ZRT_increment75... image is the recommended base;
#        the factory stock image also works)
# TAG    352 KiB ZRT tag (0x40000..0x98000)
# KERNEL uImage.jzlzma, <= 2560 KiB (0x98000..0x318000)
# ROOTFS jzlzma container, <= 5 MiB (0x318000..0x818000)
# OUT    resulting 16 MiB image
set -eu

if [ "$#" -ne 5 ]; then
	echo "usage: $0 BASE TAG KERNEL ROOTFS OUT" >&2
	exit 2
fi

python3 - "$1" "$2" "$3" "$4" "$5" <<'PY'
import hashlib, os, sys

base_p, tag_p, ker_p, rfs_p, out_p = sys.argv[1:6]

TAG_OFF, TAG_SLOT = 0x40000, 0x58000
KER_OFF, KER_SLOT = 0x98000, 0x280000
RFS_OFF, RFS_SLOT = 0x318000, 0x500000
IMG = 16 * 1024 * 1024

base = bytearray(open(base_p, "rb").read())
if len(base) != IMG:
	sys.exit(f"BASE must be {IMG} bytes (got {len(base)})")

tag = open(tag_p, "rb").read()
ker = open(ker_p, "rb").read()
rfs = open(rfs_p, "rb").read()

for name, blob, slot in (("TAG", tag, TAG_SLOT),
                         ("KERNEL", ker, KER_SLOT),
                         ("ROOTFS", rfs, RFS_SLOT)):
	if len(blob) > slot:
		sys.exit(f"{name} too large: {len(blob)} > {slot} bytes")

base[TAG_OFF:TAG_OFF + TAG_SLOT] = b"\xff" * TAG_SLOT
base[TAG_OFF:TAG_OFF + len(tag)] = tag

base[KER_OFF:KER_OFF + KER_SLOT] = b"\xff" * KER_SLOT
base[KER_OFF:KER_OFF + len(ker)] = ker

base[RFS_OFF:RFS_OFF + RFS_SLOT] = b"\xff" * RFS_SLOT
base[RFS_OFF:RFS_OFF + len(rfs)] = rfs

os.makedirs(os.path.dirname(os.path.abspath(out_p)) or ".", exist_ok=True)
with open(out_p, "wb") as f:
	f.write(base)

h = hashlib.md5(base).hexdigest()
s = hashlib.sha256(base).hexdigest()
print(f"wrote {out_p} ({len(base)} bytes)")
print(f"  base      : {base_p}")
print(f"  tag       : {tag_p} ({len(tag)} B)")
print(f"  kernel    : {ker_p} ({len(ker)} B)")
print(f"  rootfs    : {rfs_p} ({len(rfs)} B)")
print(f"  md5       : {h}")
print(f"  sha256    : {s}")
PY
