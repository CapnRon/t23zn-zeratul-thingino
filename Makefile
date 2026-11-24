# T23ZN ZRT + thingino firmware build (OS02G10)
#
# Two modes:
#   - image-only (no SDK needed): uses the pinned payloads in artifacts/
#   - source build: set SDK_DIR / KERNEL_DIR / TC (and ROOTFS_STAGING for rootfs)
#
# Examples:
#   make image
#   make verify
#   make flash OUT=out/ZRT_custom.bin
#   make check SDK_DIR=/path/to/zeratul-sdk/Software
#   make sensor kernel SDK_DIR=... KERNEL_DIR=...
#   make tag TAG_BASE=factory_tag.bin TAG_GENERATOR=...
#   make rootfs ROOTFS_STAGING=/path/to/thingino-rootfs
#   make image KERNEL=out/uImage.jzlzma ROOTFS=out/rootfs.jzlzma
#
SHELL := /bin/sh
JOBS  ?= $(shell nproc 2>/dev/null || echo 4)

# External source trees (not redistributed; see README "Build from scratch")
SDK_DIR       ?=
THINGINO_DIR  ?=
RAPTOR_DIR    ?=
HAL_DIR       ?= $(RAPTOR_DIR)/hal
IPC_DIR       ?= $(RAPTOR_DIR)/ipc
COMMON_DIR    ?= $(RAPTOR_DIR)/common
COMPY_DIR     ?= $(RAPTOR_DIR)/compy

TC            ?= $(SDK_DIR)/../toolchain/mips-gcc540-uclibc0.9.33.2-64bit-r3.3.0.smaller/bin/mips-linux-uclibc-
KERNEL_DIR    ?= $(SDK_DIR)/kernel/kernel
TAG_GENERATOR ?= $(SDK_DIR)/../make_tag/tools/make_tag/tag_generator/tag_generator_t23_host

# Rootfs staging assembled from the thingino target + rootfs-overlay +
# artifacts/raptor-v5 + the kernel modules (see docs/PINNED_BUILD_increment75.md).
ROOTFS_STAGING ?=

# Pinned payloads (defaults = the pinned build)
BASE_IMAGE ?= artifacts/ZRT_increment75_os02g10_rsd5.bin
TAG        ?= artifacts/tag_os02g10_1920_rmem28.bin
KERNEL     ?= artifacts/kernel_increment75_os02g10.uImage.jzlzma
ROOTFS     ?= artifacts/rootfs_increment75_thingino_raptor5.cpio.jzlzma

# Tag env/cmdline used by `make tag`
TAG_CMDLINE ?= console=ttyS1,115200n8 mem=36M@0x0 rmem=28M@0x2400000 root=/dev/ram0 rw rdinit=/linuxrc mtdparts=jz_sfc:256K(boot),352K(tag),2560K(kernel),5M(rootfs),8096K(data),16M@0(all) lpj=6955008 quiet
TAG_BASE    ?= artifacts/tag_os02g10_1920_rmem28.bin
DATA_ROOT   ?= data-overlay
DATA_SIZE   ?= 0x7e8000
DATA        ?= $(OUT_DIR)/data.jffs2
OVERLAY_TAG    ?= $(OUT_DIR)/tag.bin
OVERLAY_KERNEL ?= $(OUT_DIR)/uImage.jzlzma
OVERLAY_ROOTFS ?= $(OUT_DIR)/rootfs.jzlzma
OVERLAY_OUT    ?= $(OUT_DIR)/ZRT_overlay.bin
TAG_ENV     ?= senv;[HW];init_vw=1920;init_vh=1080;nrvbs=1;[IR];ir_mode=auto;ir_led=auto;[AUDIO];mic=on;[VIDEO];antiflicker=2;flip=off;[IVS];sense=3;clip_length=10;retrigger_time=30;[IOT];ZONE=Asia/Hong_Kong;TZ=HKT-8;fac=0;[DEV];device_type=4;[PMODE];pmode=1;[WIFI];SSID2=;PASS2=;eenv;

OUT_DIR ?= out
OUT     ?= $(OUT_DIR)/ZRT_custom.bin

.PHONY: all image overlay-image data flash verify check sensor kernel tag rootfs clean

all: image

# --------------------------------------------------------------------------
check:
	@echo "SDK_DIR       = $(SDK_DIR)"
	@echo "KERNEL_DIR    = $(KERNEL_DIR)"
	@echo "TC            = $(TC)"
	@echo "RAPTOR_DIR    = $(RAPTOR_DIR)"
	@echo "ROOTFS_STAGING= $(ROOTFS_STAGING)"
	@command -v thingino-dfu >/dev/null || echo "WARN: thingino-dfu not found (needed for flash)"
	@command -v python3 >/dev/null || { echo "ERROR: python3 required"; exit 1; }
	@if [ -n "$(SDK_DIR)" ]; then \
		test -x "$(TC)gcc" || { echo "ERROR: cross gcc not found: $(TC)gcc"; exit 1; }; \
		test -f "$(KERNEL_DIR)/Makefile" || { echo "ERROR: kernel tree not found: $(KERNEL_DIR)"; exit 1; }; \
		echo "SDK toolchain/kernel: OK"; fi
	@echo "check done"

verify:
	@cd artifacts && sha256sum -c \
		ZRT_increment75_os02g10_rsd5.bin.sha256 \
		tag_os02g10_1920_rmem28.bin.sha256 \
		kernel_increment75_os02g10.uImage.jzlzma.sha256 \
		rootfs_increment75_thingino_raptor5.cpio.jzlzma.sha256
	@cd artifacts/raptor-v5 && sha256sum -c rvd.sha256 rsd.sha256 rhd.sha256

# --------------------------------------------------------------------------
# os02g10 sensor driver -> <kernel>/arch/mips/xburst/lib/isp-t23/os02g10.hex
sensor:
	@test -n "$(KERNEL_DIR)" || { echo "ERROR: set KERNEL_DIR=/path/to/kernel"; exit 1; }
	$(MAKE) -C drivers/sensor-t23/zeratul/os02g10 KDIR="$(KERNEL_DIR)" CROSS_COMPILE="$(TC)"
	$(MAKE) -C drivers/sensor-t23/zeratul/os02g10 KDIR="$(KERNEL_DIR)" CROSS_COMPILE="$(TC)" release

# kernel uImage (+ modules) from the pinned config
kernel:
	@test -d "$(KERNEL_DIR)" || { echo "ERROR: set KERNEL_DIR=/path/to/kernel"; exit 1; }
	@test -x "$(TC)gcc" || { echo "ERROR: set TC=/path/to/toolchain-prefix"; exit 1; }
	@if [ ! -d "$(KERNEL_DIR)/fs/overlayfs" ]; then \
		patch -d "$(KERNEL_DIR)" -p1 < "$(CURDIR)/patches/thingino-3.10-overlayfs-v18.patch"; \
	fi
	cp -f configs/kernel_increment75_os02g10.config "$(KERNEL_DIR)/.config"
	$(MAKE) -C "$(KERNEL_DIR)" ARCH=mips CROSS_COMPILE="$(TC)" olddefconfig
	$(MAKE) -C "$(KERNEL_DIR)" ARCH=mips CROSS_COMPILE="$(TC)" \
		ZRT_ENV_SENSOR=os02g10 ZRT_ENV_SENSOR_NUM=one ZRT_ENV_IVDC_MODE=un-direct \
		uImage -j$(JOBS)
	$(MAKE) -C "$(KERNEL_DIR)" ARCH=mips CROSS_COMPILE="$(TC)" modules -j$(JOBS)
	@mkdir -p "$(OUT_DIR)"
	cp -f "$(KERNEL_DIR)/arch/mips/boot/uImage.jzlzma" "$(OUT_DIR)/uImage.jzlzma"
	@echo "kernel payload: $(OUT_DIR)/uImage.jzlzma"

# update the vendor tag with the pinned env/cmdline (needs the SDK host tool)
tag:
	@test -n "$(TAG_GENERATOR)" && test -n "$(TAG_BASE)" || { \
		echo "ERROR: set TAG_GENERATOR=/path/to/tag_generator_t23_host TAG_BASE=/path/to/factory_tag.bin"; exit 1; }
	@mkdir -p "$(OUT_DIR)"
	scripts/update_tag.sh "$(TAG_GENERATOR)" "$(TAG_BASE)" "$(OUT_DIR)/tag.bin" "$(TAG_ENV)" "$(TAG_CMDLINE)"
	@echo "tag payload: $(OUT_DIR)/tag.bin"

# build the 5 MB rootfs container from a staging tree
rootfs:
	@test -n "$(ROOTFS_STAGING)" || { \
		echo "ERROR: set ROOTFS_STAGING=/path/to/thingino-rootfs (with rootfs-overlay applied)"; exit 1; }
	@mkdir -p "$(OUT_DIR)"
	scripts/build_rootfs_container.sh "$(ROOTFS_STAGING)" "$(OUT_DIR)/rootfs.jzlzma"
	@echo "rootfs payload: $(OUT_DIR)/rootfs.jzlzma"

# --------------------------------------------------------------------------
image:
	@mkdir -p "$(OUT_DIR)"
	scripts/assemble_factory_image.sh "$(BASE_IMAGE)" "$(TAG)" "$(KERNEL)" "$(ROOTFS)" "$(OUT)"
	@ls -la "$(OUT)"

data:
	@mkdir -p "$(OUT_DIR)"
	scripts/build_data_jffs2.sh "$(DATA_ROOT)" "$(DATA)" "$(DATA_SIZE)"

overlay-image: data
	@mkdir -p "$(OUT_DIR)"
	scripts/assemble_overlay_data_image.sh "$(BASE_IMAGE)" "$(OVERLAY_TAG)" "$(OVERLAY_KERNEL)" "$(OVERLAY_ROOTFS)" "$(DATA)" "$(OVERLAY_OUT)"

flash:
	@test -f "$(OUT)" || { echo "ERROR: $(OUT) not found (make image first)"; exit 1; }
	thingino-dfu --alt flash -w "$(OUT)" --verify

clean:
	rm -rf "$(OUT_DIR)"
	-$(MAKE) -C drivers/sensor-t23/zeratul/os02g10 clean

# --------------------------------------------------------------------------
# Documentation of the pinned build:
#   docs/PINNED_BUILD_increment75.md
