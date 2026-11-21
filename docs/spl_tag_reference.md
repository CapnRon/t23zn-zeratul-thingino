# SPL / Tag behavioral reference — T23ZN Zeratul

Closed Zeratul SPL: `boot.bin` first ~32 KB (`boot_SOC_T23Z_NOR_V1.bin`,
version string `230911-T23ZN-907c2e1-MP` for T23Z). All findings from
hardware testing on the Wansview A1 (T23ZN, W25Q128 16 MB NOR).

## Boot flow (observed)

1. ROM TPL: `T31 TPL / TPL: DDR up / TPL: SPL loaded, jumping` (USB boot:
   `TPL: return to ROM` → DFU loader)
2. SPL prints `Ver:230911-T23ZN-907c2e1-MP`
3. SPL parses the tag partition (0x40000): head/taginfo/sensor-init/cmdline/
   env/bootinfo sections
4. SPL probes the sensor over i2c (prints `i2c address mismatch` when the
   tag's sensor differs from the device's)
5. SPL checks the config partition (0x80000-ish tail inside the tag region;
   formats it on first boot: `Format config partition...`)
6. SPL reads the rootfs partition per bootinfo, decompresses to
   `rd_start=0x80600000`, appends `lzo_size=<n> rd_start=<addr>
   rd_size=<n>` to the cmdline
7. SPL jumps to the kernel (loaded per the bootinfo kernel field)

## Rootfs error codes (boot fails → `goto normal boot` → ISVP u-boot)

| Error | Trigger |
| --- | --- |
| `rootfs error 0xffffffff` | nothing readable at the bootinfo rootfs offset |
| `rootfs error 0x0` | jzlzma container present but the bootinfo **rootfs size ≠ 3M** (the SPL's compiled partition size) |
| `rootfs error 0x1a0a0d00` | raw lzop stream (lzop magic `00 0d 0a 1a` read as the error value) — the SPL wants the marked jzlzma container, not lzop |
| no error, silent hang | container accepted (marker ok) but the decompress/load of an oversized stream stalls — thingino's 6.2 MB-comp/15.7 MB-decomp stream hung; ≤ 3.7 MB-decomp streams work |

## The rd_start/rd_size trap (the main debugging saga)

If the tag cmdline contains `rd_start`/`rd_size`, the SPL assumes the caller
pre-loaded the initrd into RAM (the TFTP/USB dev path) and **skips its rootfs
partition handling entirely**. It appends `lzo_size=0` (nothing loaded) plus
the caller's params. The kernel then finds no initrd:
`Initrd not found or empty - disabling initrd` → `Kernel panic: VFS: Unable
to mount root fs on unknown-block(1,0)`.

The SPL injects its own values after decompressing; the vendor's runtime
cmdline (`… lzo_size=0 rd_start=0x80600000 rd_size=<container orig>`) shows
the injected pair. Never write these into the tag cmdline.

## Bootinfo validation

`rootfs=<size>M@<offset>`: the SPL validates the rootfs slot against its
compiled expectations. Accepted: `3M@0x598000` (its built-for value).
Rejected: `6M@0x598000`, `8M@0x2D8000` → `rootfs error 0x0` even with a
valid container at the offset. `K`-suffix sizes are rejected outright
(`rootfs error 0x0` with any container). Kernel field `5M@0x98000` passes.

## Successful-boot reference (verbose, SDK rootfs)

```
Ver:230911-T23ZN-907c2e1-MP
i2c address mismatch
Initial ramdisk at: 0x80600000 (4929536 bytes)
Memory: 25296k/36864k available (3559k kernel code, 11568k reserved, ...)
Trying to unpack rootfs image as initramfs...
Freeing initrd memory: 4812K (80600000 - 80ab3000)
jz_sfc Build : ... / id code = ef4018 / WIN25Q128
nor flash quad mode is set, cmd = 6b
8 cmdlinepart partitions found on MTD device jz_sfc
Format config partition...
Erasing 32 Kibyte @ 80000 - 100% complete.
zram0: detected capacity change from 0 to 16777216
Adding 16380k swap on /dev/zram0.
Zeratul login:
```

Note `lzo_size=0` is appended by the SPL in successful boots too — it is
not the rootfs failure indicator; the absence of `Initial ramdisk at:` in
the kernel log is.
