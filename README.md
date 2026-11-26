# T23ZN Zeratul-thingino Firmware

Custom firmware for the Wansview A1 (T23ZN, **OS02G10**, ATBM6461, 16 MB NOR)
running the **thingino userspace inside the Ingenic Zeratul fast-boot chain**.

Status: **increment 75 is the pinned video build** — thingino runs inside the
Zeratul SPL → tag → kernel → initrd path with WiFi provisioning/persistence,
and both **RTSP (H.264 1920×1080)** and **MJPEG/snapshots** work from Raptor v5
(`rsd`/`rhd`). See `docs/PINNED_BUILD_increment75.md`; WiFi details in
`docs/WIFI_PROVISIONING.md`. The WebRTC GUI preview (`rwd`) is the remaining
piece.

## What's proven (on hardware, T23ZN dev board)

| Piece | Evidence |
| --- | --- |
| Zeratul SPL loads the rootfs itself when the tag cmdline has **no** `rd_start`/`rd_size` | 2H/2F-final boots; with the params present the SPL skips the load and the kernel panics with no initrd (`Initrd not found or empty`) |
| Regenerated tag (all original field values) passes SPL validation | 2G: working image + our tag → full boot, no `rootfs error` |
| thingino-branch kernel (`x-3.10.14-Archon`, jzlzma) boots via the Zeratul tag bootinfo | increment 1: full boot to login with the SDK rootfs |
| thingino rootfs as jzlzma initrd unpacks and runs | increment 2 final: initramfs unpack, rcS, `root@ing-wansview-a1-` shell |
| SPL rootfs formats: **rejects** raw lzop (error = the lzop magic bytes), accepts the marked jzlzma container | 2D vs X2/2C/2E |
| SPL rootfs size envelope: proven at ≤ 4,929,536 B decompressed; trimmed thingino (3,711,488 B) fits | 2F-final boot |

## Repository layout

```
Makefile        top-level build (image, kernel, sensor, tag, rootfs, flash)
docs/           build notes, tag/SPL behavioral reference, pinned builds
artifacts/      flashable images + kernel/rootfs payloads + tags (see hashes below)
configs/        kernel config for pinned builds
drivers/        Zeratul sensor drivers (os02g10 port)
rootfs-overlay/ boot/provisioning/streamer config restored from the config partition
scripts/        tag generation / image assembly helpers used in testing
```

## Flashable images

| File | md5 | Contents |
| --- | --- | --- |
| `artifacts/ZRT_increment75_os02g10_rsd5.bin` | `9a149caa61e7bea2b2230aede8ba27aa` | **pinned video build** (2026-11-23): os02g10 ZRT kernel + Raptor v5 — RTSP `:554` H.264 1920×1080 and MJPEG/snapshots `:8443`; thingino WiFi/STA; WDT off via factory `mcu_test`. See `docs/PINNED_BUILD_increment75.md` |
| `artifacts/ZRT_increment42_status_ioctl.bin` | `5d45e39235348bf38e5aab81bbbaf98e` | WiFi baseline: 6M rootfs layout, thingino userspace + overlay, ATBM6461 provisioning via `ATBM_STATUS` ioctl, client persistence across MCU reset, portal/password fixes |
| `artifacts/increment2_final.bin` | `a265e21be5bfd3989fca144e1adf6036` | increment-2 minimal rootfs (busybox init + dropbear), historical |
| `artifacts/ZRT_SOC_T23Z_GC2063_UNDIRECT_FW.bin` | `1db5ece5…` | SDK sample replicated through the documented build (increment-2-era layout, boots to `Zeratul login:`) |

## Kernel / rootfs payloads

| File | md5 | Notes |
| --- | --- | --- |
| `kernel_thingino_t23zeratul.uImage.jzlzma` | see `.sha256` files | thingino-linux branch `T23-zeratul-20230916`, defconfig `zeratul_SOC_T23Z_NOR_camera_IIC_V1_defconfig`, `uImage.jzlzma` (2,189,296 B) |
| `rootfs_minimal_thingino.cpio.jzlzma` | see `.sha256` files | thingino A1 target, trimmed to busybox-init + dropbear; container: `[comp_size][0x27051956][dict 0x10000][orig_size]` + lzma payload |

## Critical findings (the debugging trail)

1. **The SPL skips its rootfs decompress if the tag cmdline contains
   `rd_start`/`rd_size`** — it assumes the caller pre-loaded the initrd
   (TFTP/USB dev path). It appends `lzo_size=0 rd_start=… rd_size=<container
   orig>` and boots with no initrd → kernel panic `VFS: Unable to mount root
   fs`. Fix: never put those params in the tag cmdline; the SPL injects them
   itself after decompressing the rootfs partition.
2. **The SPL's rootfs loader only accepts the marked jzlzma container**
   (`[comp_size][0x27051956][dict][orig_size]` + LZMA payload, produced by
   the SDK's `lzma -z -f -1` + `mark_rootfs_lzma`). Raw lzop is rejected with
   `rootfs error 0x1a0a0d00` (the lzop magic bytes as the error value).
3. **The SPL validates the rootfs slot against the bootinfo fields** —
   `rootfs=6M@0x598000` / `8M@0x2D8000` → `rootfs error 0x0`;
   `3M@0x598000` (the value it was built for) passes. Non-3M partitions are
   rejected by this SPL build; a working rootfs must fit 3 MB compressed.
   *Superseded (increment 27+): the current image uses
   `kernel=2560K@0x98000 rootfs=6M@0x318000` and boots; the 3 MB limit was
   specific to the earlier tag/rootfs build.*
4. **K-suffix bootinfo sizes are rejected**; `M`-suffix values pass tag
   validation (but the rootfs itself must still fit).
5. The SPL appends its computed params to the cmdline at boot
   (`lzo_size=0 rd_start=0x80600000 rd_size=<container orig>`); the vendor's
   runtime cmdline shows the same pattern.

## Build from scratch (make)

Prerequisites (not redistributed here — obtain them under their own terms):

- Ingenic **Zeratul SDK 20230916** (`SDK_DIR`): kernel, toolchain, IMP libs, tag tools.
- **thingino** buildroot target (`THINGINO_DIR`) for the rootfs base.
- **Raptor + HAL + IPC + common + compy** at the pinned commits (`RAPTOR_DIR`).
- The factory stock image for the SPL/base, or use the pinned image as the base.
- `thingino-dfu`, `python3`, and the SDK `lzma` (for the container build).

Quick image build from the committed pinned payloads — no SDK needed; this
reproduces `artifacts/ZRT_increment75_os02g10_rsd5.bin` byte-for-byte:

```sh
make image                 # base + pinned tag/kernel/rootfs -> out/ZRT_custom.bin
make verify                # check the artifact hashes
make flash OUT=out/ZRT_custom.bin
```

Source builds (with the SDK / thingino / Raptor trees available):

```sh
make check SDK_DIR=... RAPTOR_DIR=...
make sensor kernel SDK_DIR=... KERNEL_DIR=...
make tag TAG_GENERATOR=... TAG_BASE=/path/to/factory_tag.bin
make staging THINGINO_ROOTFS=/path/to/thingino-target-rootfs \
  ROOTFS_STAGING=/path/to/rootfs-staging KERNEL_MODULES=/path/to/modules
make rootfs ROOTFS_STAGING=/path/to/rootfs-staging
make image KERNEL=out/uImage.jzlzma TAG=out/tag.bin ROOTFS=out/rootfs.jzlzma
```

The os02g10 driver is in `drivers/sensor-t23/zeratul/os02g10/`; the kernel
config is `configs/kernel_increment75_os02g10.config`. `rootfs-overlay/` holds
the boot/provisioning/streamer configuration; it contains **no credentials**
(WiFi is provisioned via the portal or `/etc/wpa_supplicant.conf`).

Full instructions, tag splits, boot order and failure modes:
`docs/BUILD_FROM_SCRATCH.md`.

**Licensing/redistribution:** the Ingenic SDK, toolchain, IMP libraries and the
ATBM6461 driver are proprietary and must not be vendored here; the thingino
components are GPL. The SDK-derived artifacts are provided for this device
only.

## Build procedure

See `docs/BUILD_NOTES.md` for the full validated SDK build. Kernel source:
thingino-linux branch `T23-zeratul-20230916` (the vendored SDK kernel),
defconfig `zeratul_SOC_T23Z_NOR_camera_IIC_V1_defconfig`, target
`make … uImage` then `cp arch/mips/boot/uImage.jzlzma …`.

Rootfs: thingino buildroot target → rsync to a staging dir → trim →
`find . -print0 | cpio -o -H newc --null` → SDK `lzma -z -k -f -1` →
`mark_rootfs_lzma jz_lzma_out.bin out.cpio.jzlzma`.

Tag: SDK `tag_generator_t23_host --create` — **cmdline must not contain
`rd_start`/`rd_size`**; bootinfo `kernel=5M@0x98000 rootfs=3M@0x598000`.

## Current build (increment 42)

Layout: `boot 256K@0`, `tag 352K@0x40000`, `kernel 2560K@0x98000`,
`rootfs 6M@0x318000`, `recovery 2560K@0x918000`, `system 4000K@0xB98000`,
`config 512K@0xF80000`.

Base rootfs: thingino target
`wansview_a1_t23zn_os02g10_atbm6461-3.10.14-uclibc`; overlay files in
`rootfs-overlay/`. Rebuild:

```sh
scripts/build_rootfs_container.sh <rootfs-dir> <out.jzlzma> [sdk-lzma]
scripts/assemble_increment.sh <base-16MiB-image> <out.jzlzma> <out.bin>
```

The container magic is **little-endian** (`struct.pack('<I', 0x27051956)`).
`docs/WIFI_PROVISIONING.md` covers the WiFi/provisioning/overlay design and
the increment-42 hardware evidence.

## Known issues (increment 42)

- `rvd` fails with `no ring after 5s`: `tx_isp_t23`, `sensor_os02g10_t23` and
  `audio` are missing from `modules.dep` — next item for video.
- WiFi is MCU-managed (stock ATBM6461 firmware); the host-managed
  `wpa_supplicant` path is not used.
- A mid-run AP→STA switch leaves the MCU datapath broken (only the MCU's own
  stack answers). A clean STA boot forwards TCP/ICMP; provisioning ends with
  an MCU reset for that reason.

## Preview and timeline

- `/preview.html` — SD archive player; no live stream
- `/timeline.html`, `/timeline_standalone.html` — recorded clip timeline
- `/x/timeline.cgi`, `recordings.cgi`, `latest-recording.cgi` — JSON clip lists
- `/x/video.cgi?path=...` — SD mp4 playback; Range header best-effort

Requires SD mount and rmr; read GET is open, POST requires auth. Timezone offset defaults to UTC+8 and can be stored in `/data/root/etc/clock/timezone`.
