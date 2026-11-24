#!/bin/sh
# Update a vendor ZRT tag's env/cmdline (and CRC) with the SDK host tool.
#
#   update_tag.sh TAG_GENERATOR BASE_TAG OUT_TAG [ENV] [CMDLINE]
#
# BASE_TAG must be a factory/vendor tag carrying the os02g10 SENS section,
# sensor calibration and RISC-V firmware (e.g. extracted from the stock image
# at 0x40000, 352 KiB). Generating a tag from scratch without the vendor
# sensor setting makes the SPL loop ("Ver:" repeats).
set -eu

if [ "$#" -lt 3 ]; then
	echo "usage: $0 TAG_GENERATOR BASE_TAG OUT_TAG [ENV] [CMDLINE]" >&2
	exit 2
fi

GEN=$1
BASE=$2
OUT=$3
ENV=${4:-senv;[HW];init_vw=1920;init_vh=1080;nrvbs=1;[IR];ir_mode=auto;ir_led=auto;[AUDIO];mic=on;[VIDEO];antiflicker=2;flip=off;[IVS];sense=3;clip_length=10;retrigger_time=30;[IOT];ZONE=Asia/Hong_Kong;TZ=HKT-8;fac=0;[DEV];device_type=4;[PMODE];pmode=1;[WIFI];SSID2=;PASS2=;eenv;}
CMDLINE=${5:-console=ttyS1,115200n8 mem=36M@0x0 rmem=28M@0x2400000 root=/dev/ram0 rw rdinit=/linuxrc mtdparts=jz_sfc:256K(boot),352K(tag),2560K(kernel),5M(rootfs),2560K(recovery),672K(common),4M(system),768K(config),16M@0(all) lpj=6955008 quiet}

cp -f "$BASE" "$OUT"
"$GEN" --update --tag_path "$OUT" --cmdline "$CMDLINE" --env "$ENV" >/dev/null
echo "wrote $OUT"
sha256sum "$OUT"
