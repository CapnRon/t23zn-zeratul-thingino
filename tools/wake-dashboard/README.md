# Host-side tools

## tools/wake-dashboard

LAN dashboard that owns the ATBM keepalive socket and wakes a sleeping camera.

- `app.py` — HTTP API/UI (default :8088) + MCU keepalive listener (:12911).
- `wake.py` — reads `wake_frame.hex` (16-byte captured CMD_WAKEUP frame; NOT in git).
- `thingino/zrt-wake-prov` — RTOS cmd 0x3f helper, installed on the camera as
  `/usr/bin/zrt-wake-prov` and run at boot by `S98wakeprov`.

Install: `systemctl enable --now zrt-wake-dashboard.service`.
The wake frame is per-device: copy `analysis/keepalive/wake_frame.hex` to the
dashboard directory on the machine that runs it.
