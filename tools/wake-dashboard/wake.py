"""Wake-frame construction.

P0/P1 status: the MCU keepalive receive path (`keeplive_decrypt_recvbuf`) has not
yet been reversed, so no wake frame is emitted. `build_wake_frame` returns None and
the API reports `unavailable`.

When P1 completes, drop the frame into `wake_frame.hex` (hex, optional whitespace)
or set it below. Optionally per-camera frames can be keyed by device_id.
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
FRAME_FILE = os.path.join(BASE, "wake_frame.hex")

# Optional per-device frames: {"WVCF7ETPUNY10MPO": "deadbeef..."}
FRAMES = {}


def _load():
    if os.path.exists(FRAME_FILE):
        try:
            raw = open(FRAME_FILE).read()
            return bytes.fromhex("".join(raw.split()))
        except Exception:
            return None
    return None


_CACHED = None
_CACHED_MTIME = None


def build_wake_frame(cam):
    """Return raw bytes to write on the MCU keepalive socket, or None."""
    global _CACHED, _CACHED_MTIME
    did = (cam or {}).get("device_id")
    if did and did in FRAMES:
        return bytes.fromhex(FRAMES[did])
    try:
        mtime = os.path.getmtime(FRAME_FILE)
    except OSError:
        return None
    if _CACHED is None or mtime != _CACHED_MTIME:
        _CACHED = _load()
        _CACHED_MTIME = mtime
    return _CACHED
