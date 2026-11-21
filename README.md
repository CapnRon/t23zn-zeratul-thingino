# T23ZN Zeratul-thingino Firmware

Custom firmware for the Wansview A1 (T23ZN, GC2063, ATBM6461, 16 MB NOR) running
the **thingino userspace inside the Ingenic Zeratul fast-boot chain**.

Status: **increment 2 complete** — thingino boots to a root shell through the
Zeratul SPL → tag → kernel → initrd path, fully validated on hardware.

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
docs/           build notes, tag/SPL behavioral reference
artifacts/      flashable images + kernel/rootfs payloads (see hashes below)
scripts/        tag generation / image assembly helpers used in testing
```

## Flashable images

| File | md5 | Contents |
| --- | --- | --- |
| `artifacts/increment2_final.bin` | `a265e21be5bfd3989fca144e1adf6036` | **current working build**: vendor SPL, our tag (no rd params), thingino kernel, minimal thingino rootfs (busybox init + dropbear), vendor recovery/system |
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
4. **K-suffix bootinfo sizes are rejected**; `M`-suffix values pass tag
   validation (but the rootfs itself must still fit).
5. The SPL appends its computed params to the cmdline at boot
   (`lzo_size=0 rd_start=0x80600000 rd_size=<container orig>`); the vendor's
   runtime cmdline shows the same pattern.

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

## Known issues in the current minimal image

- initrd `/dev` is empty → `can't open /dev/null` noise before mdev
- `fw_printenv` and `etc/init.d/lib-serial-mac` were trimmed out (scripts
  reference them)
- No wifi (ATBM6461 ko + wpa_supplicant pending), no streaming (prudynt +
  libimp pending), no persistent overlay (configs are RAM-only)
