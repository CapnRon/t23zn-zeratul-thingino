#!/bin/bash
# Assemble a T23ZN Zeratul-thingino flash image from partition payloads.
#
# Usage: assemble_image.sh <out.bin> <kernel.jzlzma> <rootfs.cpio.jzlzma> [tag.bin]
#
# Layout (16 MB NOR, the validated incremental layout):
#   boot     0x000000  256K   vendor Zeratul SPL (from the SDK sample image)
#   tag      0x040000  352K   generated (no rd_start/rd_size in the cmdline!)
#   kernel   0x098000  5M     thingino uImage.jzlzma
#   rootfs   0x598000  3M     thingino rootfs cpio.jzlzma (must fit 3 MB!)
#   recovery 0x898000  2560K  vendor recovery
#   system   0xB18000  4512K  vendor system
#
# The SPL loads the rootfs itself (decompresses jzlzma to 0x80600000);
# the tag cmdline must NOT contain rd_start/rd_size (see README findings).
set -euo pipefail

OUT=$1; KERNEL=$2; ROOTFS=$3; TAG=${4:-}
SDK_SAMPLE=${SDK_SAMPLE:-SDK_sample_image.bin}   # vendor image for boot/recovery/system

for f in "$SDK_SAMPLE" "$KERNEL" "$ROOTFS"; do [ -f "$f" ] || { echo "missing: $f"; exit 1; }; done

if [ -z "$TAG" ]; then
	echo "generating tag (no rd params)..."
	here=$(cd "$(dirname "$0")" && pwd)
	pushd "$here/../tools/make_tag/tag_generator" > /dev/null
	./tag_generator_t23_host --create --tag_path=tag_assembled.bin \
		--cmdline="console=ttyS1,115200n8 mem=36M@0x0 rmem=28M@0x2400000 root=/dev/ram0 rw rdinit=/linuxrc mtdparts=jz_sfc:256K(boot),352K(tag),5M(kernel),3M(rootfs),2560K(recovery),4512K(system),512k(config),16M@0(all) lpj=4493312 senv;[HW];init_vw=2048;init_vh=1536;nrvbs=2;mode=0;pwm_duty=20;pwm_freq=80000;eenv;" \
		--bootinfo="kernel=5M@0x98000 rootfs=3M@0x598000" \
		--env="senv;[HW];init_vw=2048;init_vh=1536;nrvbs=2;mode=0;pwm_duty=20;pwm_freq=80000;eenv;" \
		--sensor_init=gc2063_t23_init.bin \
		--fwinfo="ZRT_release_build;[VERSION];ver=CAMERA_SOC_T23Z_gc2063_V;" \
		--sensor_setting_mode0=../sensor_calibration_bin/gc2063_t23.bin \
		--aetab=../sensor_start_ae_table/ae_table_gc2063.bin
	popd > /dev/null
	TAG="$here/../tools/make_tag/tag_generator/tag_assembled.bin"
fi

python3 - "$SDK_SAMPLE" "$TAG" "$KERNEL" "$ROOTFS" "$OUT" << 'PYEOF'
import sys, hashlib
sdk, tag, kernel, rootfs, out = (open(f,'rb').read() for f in sys.argv[1:6])
img = bytearray(b'\xff'*16*1024*1024)
img[0x000000:0x040000] = sdk[0x000000:0x040000]           # boot (vendor SPL)
img[0x040000:0x098000] = tag[:0x58000]                     # tag
img[0x098000:0x098000+len(kernel)] = kernel                # kernel
img[0x598000:0x598000+len(rootfs)] = rootfs                # rootfs
img[0x898000:0xB18000] = sdk[0x898000:0xB18000]            # recovery (vendor)
img[0xB18000:len(sdk)] = sdk[0xB18000:len(sdk)]            # system (vendor, partial)
assert b'rd_start' not in tag, 'rd_start/rd_size in tag cmdline breaks the SPL rootfs load!'
open(out,'wb').write(bytes(img))
print(out, len(img), hashlib.md5(bytes(img)).hexdigest())
PYEOF
echo "done: $OUT"