# Pinned build — ZRT_increment75 (os02g10, RTSP + MJPEG)

Pinned on 2026-11-23. This is the last known-good build with **working RTSP and
MJPEG** on the Wansview A1 (T23ZN, **OS02G10**, ATBM6461, 16 MB NOR).

```
artifacts/ZRT_increment75_os02g10_rsd5.bin
  size    16,777,216 B
  md5     9a149caa61e7bea2b2230aede8ba27aa
  sha256  2982dec301612f1865891bf0fd05dc51cbbcdde6d8074c097e0292e4ea6b4bb0
```

Do not confuse this with the earlier GC2063-era images: the real sensor is
**OS02G10**. The increment42 image (`5d45e392…`) is the WiFi baseline only.

---

## 1. What this build is

Boot chain: **factory ZRT SPL → factory/vendor ZRT tag → Zeratul-SDK kernel
(3.10.14-Archon) built with os02g10 → thingino rootfs (uClibc-ng)**.

| Component | Value |
| --- | --- |
| Kernel | Zeratul SDK 3.10.14, `zeratul_SOC_T23Z_NOR_camera_IIC_V1_defconfig` + os02g10/wireless/MMC1 config (see `configs/kernel_increment75_os02g10.config`) |
| Sensor driver | os02g10 ported into the Zeratul sensor framework — `drivers/sensor-t23/zeratul/os02g10/` |
| Tag | `artifacts/tag_os02g10_1920_rmem28.bin` (vendor SENS + 176288 B calibration + RISC-V FW; env `init_vw=1920 init_vh=1080 nrvbs=1`; cmdline `mem=36M@0x0 rmem=28M@0x2400000`) |
| Rootfs | thingino (uClibc-ng 1.0.58) + Raptor **v5** (`rvd`, `rsd`, `rhd`), thingino jzmmc with `cd_gpio_pin=61`, factory `mcu_test --wdt_disable`, wireless stack |
| Layout | factory: boot 256K@0 · tag 352K@0x40000 · kernel 2560K@0x98000 · rootfs 5M@0x318000 · recovery 2560K@0x818000 · common 672K@0xA98000 · system 4M@0xB40000 · config 768K@0xF40000 |

### Proven on hardware

- Boots to the thingino userspace; overlay on mtd7; WiFi STA via the ATBM MCU.
- **RTSP**: `rtsp://thingino:thingino@<ip>:554/ch0` → H.264 **1920×1080** +
  AAC, title `Raptor Live`; sub stream `ch1`.
- **MJPEG**: `http://thingino:thingino@<ip>:8443/mjpeg` →
  `multipart/x-mixed-replace;boundary=raptorframe`, parts ~250 KB JPEG.
  Sub: `/mjpeg?stream=1`; snapshots `/snap.jpg` and `/snap.jpg?stream=1`
  (1920×1080 JPEG).
- WDT bypass relay **off**; the SoC stays up because `mcu_test --wdt_disable`
  runs in `S09mmc`.
- Validated unit was `192.168.2.128` (ATBM STA MAC `38:77:07:e3:68:1a`).

### Not in this build

- GUI live preview (`/preview.html`, native WebRTC) does **not** work: it needs
  the Raptor `rwd` at v5, and the rwd in this rootfs is the prebuilt v3. See
  "Remaining work".
- MJPEG main stream is ~1 fps (main-stream JPEG ring); use the sub for speed.
- Image quality/AE not tuned; the vendor calibration is carried in the tag.
- No WiFi credentials are stored in the repository — provision the unit
  (portal or `/etc/wpa_supplicant.conf`), or see the private handoff.

---

## 2. Flashing

The board needs the DFU relay/console setup (`HANDOFF-RELAY-DFU.md`). Summary:

```sh
# enter bootrom: main power off, WDT bypass off to drop, strap LOW, bypass ON, power on
thingino-dfu -b                 # wait ~8-10 s for the DFU alts
thingino-dfu -l                 # alts: flash / erase / reboot
thingino-dfu --alt flash -w artifacts/ZRT_increment75_os02g10_rsd5.bin --verify
# normal boot: strap HIGH, bypass OFF (GPIO5 HIGH), power-cycle
```

Relay semantics: GPIO2 LOW = bootloader enabled; GPIO3 LOW = power on; GPIO5
LOW = WDT bypass ON (keeps the SoC powered), HIGH = WDT enabled/bypass off.
A true power-cycle requires GPIO3 HIGH **and** GPIO5 HIGH while off.

On first boot the tag primary may be valid; `/etc/fw_env.config` should be a
comment-only file so `S97sysupgrade` does not overwrite the primary tag with the
U-Boot environment.

---

## 3. Rebuild recipe

The repository `Makefile` wraps these steps. `make image` with the committed
pinned payloads (`artifacts/kernel_increment75_…uImage.jzlzma`,
`artifacts/rootfs_increment75_….cpio.jzlzma`, the tag) reproduces the pinned
image byte-for-byte (verified: md5 `9a149caa…`). The source paths below are
what the `make sensor/kernel/tag/rootfs` targets run with `SDK_DIR`,
`KERNEL_DIR`, `TC`, `RAPTOR_DIR`, `ROOTFS_STAGING` set.

### 3.1 os02g10 sensor driver (Zeratul)

The Zeratul kernel compiles sensor drivers **into the kernel** as
`arch/mips/xburst/lib/isp-t23/<sensor>.hex`. Port the ISVP driver
(`Ingenic SDK 3.10.14/sensor-src/t23/os02g10.c`) to
`os/drivers/sensor-t23/zeratul/os02g10/` using the Zeratul gc2063 driver as the
template. The committed source is already ported; the essential differences:

- `#define SENSOR_WITHOUT_INIT`, `extern int riscv_is_pass;`, `fast_wdr_mode`
- no `module_param`/`MODULE_*`; `.owner = NULL`; no `sensor_info`,
  `sensor_common_init/exit`, `sensor_update_actual_fps`
- `get_sensor_name("os02g10")`, `get_sensor_i2c_addr(0x3c)`,
  `get_sensor_width/height`, `init_sensor`/`exit_sensor`

The repository `Makefile` in that directory takes `KDIR`/`KERNEL_DIR` and
`CROSS_COMPILE`/`TC`:

```sh
make sensor KERNEL_DIR=<kernel> TC=<sdk-toolchain>/bin/mips-linux-uclibc-
# -> <kernel>/arch/mips/xburst/lib/isp-t23/os02g10.hex
```

### 3.2 Kernel

Use the committed `configs/kernel_increment75_os02g10.config` (or the defconfig
plus these deltas):

```
JZMMC_V12=m, JZMMC_V12_MMC1=y, JZMMC_V12_MMC1_PB_4BIT=y,
MMC1_MAX_FREQ=48000000, MMC0_MAX_FREQ=48000000,
DEVTMPFS=y, DEVMEM=y,
WLAN=y, WIRELESS=y, WIRELESS_EXT=y, WEXT_CORE/PROC/PRIV=y, CFG80211=y,
MAC80211 is not set
```

The **thingino `jzmmc_v12.c`** must be used (it has `cd_gpio_pin`; the SDK one
does not). Rebuild modules (`mmc_core`, `jzmmc`, `mmc_block`, `jz_sfc`,
`jffs2`, `squashfs`) and install them with a `modules.dep` that maps
`jzmmc`/`mmc_block` to `mmc_core` and `extra/atbm6461_wifi_sdio.ko` to
`mmc_core jzmmc`.

```sh
make ARCH=mips CROSS_COMPILE=<sdk-toolchain>/bin/mips-linux-uclibc- \
     ZRT_ENV_SENSOR=os02g10 ZRT_ENV_SENSOR_NUM=one ZRT_ENV_IVDC_MODE=un-direct uImage
# -> arch/mips/boot/uImage.jzlzma
```

### 3.3 Tag

Use the committed `artifacts/tag_os02g10_1920_rmem28.bin`. It was produced from
the factory tag with the SDK host tool, preserving the vendor sensor
init/calibration/RISC-V firmware and changing only env/cmdline:

```sh
tag_generator_t23_host --update --tag_path tag_os02g10_1920_rmem28.bin \
  --cmdline "console=ttyS1,115200n8 mem=36M@0x0 rmem=28M@0x2400000 root=/dev/ram0 rw rdinit=/linuxrc mtdparts=jz_sfc:256K(boot),352K(tag),2560K(kernel),5M(rootfs),2560K(recovery),672K(common),4M(system),768K(config),16M@0(all) lpj=6955008 quiet" \
  --env "senv;[HW];init_vw=1920;init_vh=1080;nrvbs=1;…;eenv;"
```

**Do not** generate a tag from scratch without the vendor sensor setting: the
SPL loops (`Ver:` repeats) when the tag carries no valid sensor setting.

### 3.4 Raptor v5 (rsd/rhd)

Source: Raptor HEAD `5d9e2f9` (+ HAL). Compy: **55797ad** (has the APIs the
daemons use). `rhd` is HTTP-only in this build (`[http] https=false`,
`port=8443`).

```sh
make PLATFORM=T23 CROSS_COMPILE=<sdk-toolchain>/bin/mips-linux-uclibc- \
     rsd rhd EXTRA_CFLAGS="-Wno-error=pragmas" \
     LDFLAGS="-lm -lpthread -latomic -Wl,--allow-shlib-undefined"
```

Install `rsd`/`rhd` over the prebuilt v3 binaries in `/usr/bin`; they match
`rvd` v5 and the v5 `librss_common`/`librss_ipc`.

### 3.5 Rootfs

thingino target rootfs with:
- `S00devtmpfs` (devtmpfs + tmpfs `/dev/shm`), `S00overlay` (mtd7) — keep.
- `S09mmc`: load `jzmmc cd_gpio_pin=61`, PB8–PB14 pinmux, insmod
  `atbm6461_wifi_sdio`, then `/usr/bin/mcu_test --wdt_disable`
  (**factory** `mcu_test` + factory `librtos.so`; the thingino
  `z7682_disable_wdt` mismatches the factory librtos).
- `S38wpa_supplicant`: ATBM client path uses
  `mcu_test --wifi_connect="<ssid>:<psk>"` and applies the MCU DHCP lease.
- `/etc/raptor.conf`: `[stream0] 1920×1080 nr_vbs=1`; `[http] https=false port=8443`.
- `/etc/fw_env.config` comment-only (preserve the tag primary).
- The module set from §3.2.

Build the 5 MB container and assemble:

```sh
scripts/build_rootfs_container.sh <staging> out.cpio.jzlzma
# image: blank 0x318000–0x818000, write the container; tag at 0x40000; kernel at 0x98000
```

---

## 4. Known hardware/software rules

- Hardware/factory is **OS02G10**, 1920×1080 — not GC2063.
- The factory kernel's IMP (`H20231110a`) does not match the SDK libimp;
  H.264/JPEG encoders SIGFPE there. The working pair is the SDK kernel +
  SDK libimp + the os02g10 port.
- Do not send manual AT commands / MCU ioctls to the ATBM; they crash the MCU.
  Use the factory `mcu_test` paths only.
- WDT bypass relay is for flashing/WDT trouble only; normal operation uses
  `mcu_test --wdt_disable` with the relay off.
- Other cameras on the test LAN (02: MACs) are not this unit; identify by the
  ATBM STA MAC / lease.

---

## 5. Remaining work (not part of this pin)

1. `rwd` v5 for the WebRTC GUI preview: build compy 55797ad with
   `COMPY_TLS_MBEDTLS=ON` (SRTP), and librss/rwd with the Buildroot GCC 15
   uClibc-ng sysroot (`host/opt/ext-toolchain/bin/mipsel-thingino-linux-uclibc-gcc`,
   sysroot `host/mipsel-buildroot-linux-uclibc/sysroot`), rpath `/usr/lib/rwd`
   to keep the SDK librss for rvd/rsd/rhd.
   Alternatively point `/var/www/x/ch0.mjpg` at the rhd MJPEG.
2. MJPEG refresh: main ring is ~1 fps; use `?stream=1` or tune the JPEG ring.
3. AE/color/quality tuning with the vendor calibration.
4. Record the exact rootfs staging snapshot for a byte-for-byte rebuild.
