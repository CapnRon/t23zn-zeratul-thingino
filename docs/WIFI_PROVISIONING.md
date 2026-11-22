# WiFi provisioning and persistence (increment 42)

This documents the MCU-managed WiFi path used by the Zeratul-thingino build:
the stock ATBM6461 MCU firmware keeps the association and the SoC applies the
lease. It is not the host-managed `wpa_supplicant` path used by the plain
thingino image.

## Files added or changed under `rootfs-overlay/`

| Path | Purpose |
| --- | --- |
| `etc/init.d/S00devtmpfs` | mounts devtmpfs so `/dev/atbm_ioctl` (major 250, minor 10) exists |
| `etc/init.d/S00overlay` | loads `jz_sfc`/`jffs2`, mounts `mtdblock6` on `/overlay`, restores `/etc` and `/root` |
| `etc/init.d/S39atbm-lease` | reads the MCU status and configures `wlan0`; starts the portal only when the MCU is in AP mode |
| `usr/bin/atbm-provision` | portal worker: STA mode, join, lease, save, MCU reset |
| `usr/bin/atbm-status` | small static binary reading the MCU through `ATBM_STATUS` |
| `usr/bin/atbm-at` | sends an AT command through `ATBM_FW_AT_CMD` (ioctl, not the UART) |
| `usr/bin/atbm-ap` | `ATBM_WIFI_MODE` + `ATBM_AP_CFG` for the provisioning AP |
| `usr/sbin/save-config` | copies persisted files to `/overlay/etc` (includes `/etc/shadow-`) |
| `etc/profile.d/chpasswd` | first-login flow now creates `/etc/shadow-` and saves it |
| `var/www-portal/x/api.cgi` | portal save: hostname/password/timezone, `save-config`, then launch `atbm-provision` |

The base rootfs is the thingino target
`wansview_a1_t23zn_os02g10_atbm6461-3.10.14-uclibc` (its `S38wpa_supplicant`
has the `mcu_test` client path and its `S09mmc` loads the ATBM module).

## Provisioning flow

1. Unprovisioned boot: the MCU reports AP mode, S39 starts `THINGINO-<last2>`
   (`atbm-ap`), sets the MCU AP IP to `172.16.0.2`, `wlan0` to `172.16.0.1`,
   and S60 runs the portal from `/var/www-portal`.
2. The portal POSTs to `x/api.cgi`; the CGI replies first, then runs
   `atbm-provision <ssid> <pass>` detached.
3. `atbm-provision`:
   - `atbm-at "AT+WIFI_SET_MODE=STA_MODE"` — stops the MCU AP and saves STA
     mode to MCU flash.
   - `mcu_test --wifi_connect=<ssid>:<pass>` — joins and stores credentials.
   - Polls `atbm-status` until `mode=STA connected=1` and a client IP.
   - Writes the client `wpa_supplicant.conf`, saves the lease to
     `/etc/atbm_lease` and `/overlay/etc/atbm_lease`, runs `save-config`.
   - `atbm-at "AT+REBOOT"` — resets the MCU (it also resets the SoC on this
     board); a SoC `reboot` follows after 5 s if the SoC is still up.
4. After the reset the MCU cold-boots with `default_wifi_mode 0
   wifi_auto_connect 1`, joins the saved network and DHCPs. S38 restores
   client mode from the saved config; S39 reads the MCU status, applies the
   lease and starts the full UI.

## `ATBM_STATUS` ioctl

`ATBM_STATUS = _IOR(121, 2, unsigned int)` on `/dev/atbm_ioctl`, with a
packed `struct status_info`. Fields used by `atbm-status`:

| Field | Offset | Meaning |
| --- | --- | --- |
| `bconnect` | 10 | 1 = associated |
| `wifimode` | 17 | 0 = STA, 1 = AP |
| `con_event.ssid` | 32 | SSID (32 bytes, length at 64) |
| `con_event.ipaddr` | 76 | lease IP (network-order bytes) |
| `con_event.ipmask` | 80 | netmask |
| `con_event.gwaddr` | 84 | gateway |

`atbm-status` prints `mode`, `connected`, `ssid`, `ip`, `mask`, `gw`, `mac`.
This replaces the fragile `dmesg | grep hostevent` dependency. The status
ioctl works on the stock 2025-0530 driver.

## Findings that shaped the flow

- AP-mode `hostevent` lines are not leases: they can carry a non-zero bssid
  and the AP IP (`192.168.43.1` or `172.16.0.2`). Any hostevent fallback must
  reject those subnets.
- The MCU saves the mode from `AT+WIFI_SET_MODE`; `atbm-ap` (the AP fallback)
  saves AP mode. A join in progress must not be preempted by that fallback —
  hence the status-driven S39 instead of a fixed 45 s dmesg wait.
- The MCU cold boot is slow (tens of seconds). The old 45 s timeout started
  `atbm-ap`, killed the joining STA and re-saved AP mode. The status loop now
  waits up to 90 s for STA+connected+IP, and only starts the portal when the
  MCU itself reports AP.
- A mid-run AP→STA switch leaves the MCU datapath broken (only the MCU's own
  stack answers; no SoC TCP/ICMP passes). A clean STA boot forwards traffic:
  from a LAN host, ping, TCP 22 and HTTP/HTTPS 80/443 to the lease all work.
  This is why the provisioning step ends with an MCU reset.
- First-login password prompt: `/etc/profile.d/chpasswd` returns early only
  when `/etc/shadow-` exists. The portal and the console hook now create it
  and `save-config` persists it.
- Rootfs container magic is little-endian: `struct.pack('<I', 0x27051956)`
  produces `56 19 05 27`. Writing `27 05 19 56` makes the SPL treat the
  container as raw and the rootfs fails to unpack.

## Rebuilding

```sh
# 1. stage the rootfs (thingino target + rootfs-overlay/)
scripts/build_rootfs_container.sh <rootfs-dir> <out.jzlzma> [lzma-tool]
# 2. replace the 6 MiB rootfs slot at 0x318000 in a known-good image
scripts/assemble_increment.sh <base-16MiB-image> <out.jzlzma> <out.bin>
```

The SDK `lzma` used to build the container is
`Software/os/kernel.7z` → `kernel/scripts/ingenic_hardlzma/lzma`.

Partition layout in the current image: `boot 256K@0`, `tag 352K@0x40000`,
`kernel 2560K@0x98000`, `rootfs 6M@0x318000`, `recovery 2560K@0x918000`,
`system 4000K@0xB98000`, `config 512K@0xF80000`.

## Verified on hardware (increment 42)

- Unprovisioned: `ATBM: status mode=AP conn=0` → portal in seconds.
- Provisioned + MCU reset: `Starting in client mode` → `MCU DHCP IP:
  192.168.2.128` → `ATBM: status mode=STA conn=1 ip=192.168.2.128
  gw=192.168.2.1` → full UI at `https://<lease>/`.
- From another host on the same LAN: ping, TCP/22, HTTP/80, HTTPS/443 all OK.
- Hostname and timezone persist through the reset; no first-login prompt.

## Still open

`rvd` fails with `no ring after 5s` because `tx_isp_t23`,
`sensor_os02g10_t23` and `audio` are absent from `modules.dep`. That is the
next piece for the video pipeline; it is independent of WiFi provisioning.
