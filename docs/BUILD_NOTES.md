# T23ZN Zeratul firmware — validated build procedure

Date validated: 2026-11-21
Device: T23ZN (T23Z SoC, 16 MB NOR)
Result: full boot to `Zeratul login:` with a locally built image.

## Known-good artifacts

| Item | Path | md5 |
| --- | --- | --- |
| Vendor reference image | `firmware/ZRT_SOC_T23Z_GC2063_UNDIRECT_FW.bin` | `b04245025920c386272994f1340ac865` |
| Rebuilt image (validated) | `out/ZRT_SOC_T23Z_GC2063_UNDIRECT_FW.bin` | `95d888e78545bd0c6c862f3c9a69986a` |

Runtime partition hashes of the validated build (read from `/dev/mtdN` on the device):

```
mtd0 boot     48340ac2d3a730eff81271c01e1cc024   (byte-identical to vendor)
mtd1 tag      8f13be9d352f5cdc70a1d475354daf5e
mtd2 kernel   63c5a30aa514ea1fc95dee0776b0b83c
mtd3 rootfs   8781d5a110fbac9baf8aa0f6c759ba92
```

## Procedure (documented SDK flow — do not deviate)

1. Install toolchain `tools/toolchain/gcc_540/mips-gcc540-glibc222-64bit-r3.3.0.smaller.tar.bz2`
   and put its `bin/` first in `PATH`.
2. Unpack everything from the release root (`build/unpack_all.sh` equivalent):
   `7z x os/kernel.7z -o os/`, `os/rootfs.7z -o os/`, `os/uboot.7z -o os/`,
   `os/drivers.7z -o os/`, `os/busybox.7z -o os/`, `userland.7z`, `tools.7z`, `firmware.7z`.
   Note: archives contain a top-level directory name (`kernel/`, `rootfs/`, ...), so the
   Linux tree lands at `os/kernel/kernel/../` with the Makefile at `os/kernel/`.
3. `.env` requirements (each one cost a failed build when wrong):
   - no `PATH=` line (it is passed to `make` via `cat .env | xargs make` and a literal
     `$PATH` breaks host tool lookup)
   - `ZRT_ENV_KERNEL_DIR=<top>/os/kernel` (the directory containing the kernel `Makefile`)
   - `ZRT_ENV_TOOLS_DIR=<top>/tools/tools` (note the double `tools/` in this release)
   - `ZRT_ENV_FLASH_TYPE=NOR`, `ZRT_ENV_SOC_TYPE=SOC_T23Z`, `ZRT_ENV_SENSOR=gc2063`,
     `ZRT_ENV_SENSOR_NUM=one`, `ZRT_ENV_BOARD_VERSION=V1`, `ZRT_ENV_IVDC_MODE=un-direct`,
     `ZRT_ENV_KERNEL_RELEASE=3.10.14-Archon`
4. Build with the orchestrator ONLY:
   `source .env && ./build/build_camera_all.sh`
   It runs boot → tag → uImage → rootfs → recovery → system in the correct order and
   packs `out/ZRT_SOC_T23Z_GC2063_UNDIRECT_FW.bin`.

## Why hand-running the scripts fails (root cause of the earlier failure)

`build_camera_recovery.sh` runs `make <...recovery...>_defconfig` **in the same kernel
tree**, replacing `.config` (its defconfig sets `CONFIG_LOCALVERSION="-Immortal"`) and
rebuilding `uImage`. If `uImage.jzlzma` is copied to `out/camera` *after* that step, the
packed image contains the **recovery kernel** (`x-3.10.14-Immortal`) while the rootfs
modules are built for a different release → init cannot load modules → silent death
before login. The orchestrator copies each artifact at the right moment, so keep the
order intact.

## Expected boot markers (working)

- `Ver:230911-T23ZN-907c2e1-MP`
- `i2c address mismatch` — expected when the sensor on the device differs from the
  firmware's baked-in sensor (gc2063 in this build)
- `Zeratul login:` — success

## Partition layout (confirmed from `/proc/mtd` and the build scripts)

```
mtd0 boot     00040000  (256K)    @ 0x000000
mtd1 tag      00058000  (352K)    @ 0x040000
mtd2 kernel   00500000  (5M)      @ 0x098000
mtd3 rootfs   00300000  (3M)      @ 0x598000
mtd4 recovery 00280000  (2560K)   @ 0x898000
mtd5 system   00468000  (4512K)   @ 0xB18000
mtd6 config   00080000  (512K)    @ 0xF80000
```

Boot memory window: kernel decompresses at `0x80010000`; the SPL places the rootfs
at `rd_start=0x80600000` (`mem=36M@0x0 rmem=28M@0x2400000`). The camel kernel's
decompressed size must stay below 5 MB (`0x80010000 + size < 0x80600000`).
Vendor and validated builds both decompress to `0x479bb0` (4,692,912 bytes).
