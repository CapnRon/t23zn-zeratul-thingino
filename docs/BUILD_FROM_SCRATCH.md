# Build from scratch

Committed image-only path needs no SDK:

```sh
git clone -b main https://github.com/CapnRon/t23zn-zeratul-thingino
cd t23zn-zeratul-thingino
make verify
make image
```

This reproduces `artifacts/ZRT_increment75_os02g10_rsd5.bin` from pinned payloads.

## Source build prerequisites

Not redistributed here; obtain under own terms:

- Ingenic Zeratul SDK 20230916 (`SDK_DIR`): kernel, toolchain, IMP libs, tag tools.
- thingino buildroot target (`THINGINO_DIR`) with `atbm6461` support.
- Raptor + HAL + IPC + common + compy at pinned commits (`RAPTOR_DIR`).
- Factory stock image for SPL/base, or pinned image as base.
- `thingino-dfu`, `python3`, SDK `lzma`.

## 1. Kernel

```sh
export SDK_DIR=/path/to/zeratul-sdk
export KERNEL_DIR=$SDK_DIR/kernel/kernel
export TC=$SDK_DIR/../toolchain/mips-gcc540-uclibc0.9.33.2-64bit-r3.3.0.smaller/bin/mips-linux-uclibc-

cp configs/kernel_increment75_os02g10.config "$KERNEL_DIR/.config"
make -C "$KERNEL_DIR" ARCH=mips CROSS_COMPILE="$TC" olddefconfig
make -C "$KERNEL_DIR" ARCH=mips CROSS_COMPILE="$TC" \
  ZRT_ENV_SENSOR=os02g10 ZRT_ENV_SENSOR_NUM=one ZRT_ENV_IVDC_MODE=un-direct uImage -j"$(nproc)"
make -C "$KERNEL_DIR" ARCH=mips CROSS_COMPILE="$TC" modules -j"$(nproc)"
```

Config includes exFAT/FAT/VFAT/NLS_UTF8; SD recordings need these. Output:
`$KERNEL_DIR/arch/mips/boot/uImage.jzlzma`.

Module install for staging:

```sh
make -C "$KERNEL_DIR" ARCH=mips CROSS_COMPILE="$TC" modules_install INSTALL_MOD_PATH=/path/to/modules
```

Do not copy stale `modules.dep` from an old overlay; use kernel tree depmod output.

## 2. Sensor driver

```sh
make sensor KERNEL_DIR="$KERNEL_DIR" TC="$TC"
```

Installs `os02g10.hex` into kernel ISP library before kernel build.

## 3. Rootfs staging

Build thingino target rootfs (`THINGINO_DIR/output/.../target`), then:

```sh
make staging \
  THINGINO_ROOTFS=/path/to/thingino-target-rootfs \
  ROOTFS_STAGING=/path/to/rootfs-staging \
  KERNEL_MODULES=/path/to/modules \
  RAPTOR_V5=artifacts/raptor-v5
```

`scripts/build_rootfs_staging.sh` handles:

- `/lib` symlink → `usr/lib` merge (prevents `Failed to execute /linuxrc`)
- overlay apply without credentials (`etc/wpa_supplicant.conf` preserved)
- Raptor v5 binaries into `/usr/bin`
- onvif trim to keep 5 MiB container fit

## 4. Tag

Use a vendor tag carrying os02g10 SENS/calibration/RISC-V firmware.

Default pinned split: `mem=36M@0x0 rmem=28M@0x2400000`.

Higher-RAM alternative tested for recording: `mem=44M@0x0 rmem=20M@0x2c00000`.
Higher split adds headroom for rmr/NTP repair but reduces media memory.

```sh
make tag TAG_GENERATOR=/path/to/tag_generator_t23_host \
  TAG_BASE=/path/to/factory_tag.bin TAG=out/tag.bin
```

## 5. Rootfs container and image

```sh
make rootfs ROOTFS_STAGING=/path/to/rootfs-staging
make image KERNEL=/path/to/uImage.jzlzma TAG=out/tag.bin ROOTFS=out/rootfs.jzlzma
```

Container must stay ≤ 5,242,880 B. Current head image is ~5.10 MB.

## 6. Flash

```sh
make flash OUT=out/ZRT_custom.bin
```

## Boot order expectations

`rcF` runs `F*` sorted:

`F00aclip → F00ledd → F00mmc → F00raptor → F00record → F00sclock → F00storage`

Target timeline:

- rvd start ~0.65 s
- rmr RAM launch ~0.81 s
- SD mount ~2.5 s
- RAM→SD handoff ~3.1 s
- WDT disable in S09 before 10 s

`S09mmc` must load jzmmc, set MMC power, load ATBM SDIO and run
`mcu_test --wdt_disable`. Preloaded jzmmc still needs set_power.

## Clock/timeline

- `F00sclock` starts `clock-service`: MCU clock or NTP, never blocks boot.
- `F00aclip` starts `clipwatch`: journals only new clips after boot snapshot.
- `clockfix` waits 90 s, then renames pre-sync finished clips to true UTC.
- `S10clock` is fallback; skips when `/run/clock.ready` exists.
- Invalid MCU epoch (<1.6e9) must never set clock; build time remains.

## Common failures

- `/linuxrc` exec fail: `/lib` symlink was replaced by overlay rsync.
- `modprobe: module jzmmc not found`: stale overlay `modules.dep`.
- ATBM unknown symbol: jzmmc/mmc_core not loaded or MMC power not set.
- WDT reboot before S09: early F00 work exceeded 10 s.
- No recordings: SD not mounted, rmr not running, or `rmr` started before rvd ring.
- 1970 clips: invalid MCU clock or clipwatch/clockfix missing.
