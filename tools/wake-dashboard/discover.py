import ipaddress
import os
import re
import subprocess

CAM_MAC_PREFIXES = ("38:77:07",)  # ATBM6461 WiFi MAC on the ZRT/Wansview units
NAME_HINTS = ("zrt", "thingino", "wansview", "t23", "atbm", "microscope")
# Only cameras on these subnets belong to the ZRT fleet (comma separated).
ZRT_SUBNETS = tuple(n for n in os.environ.get("ZRT_SUBNETS", "192.168.2.0/24").split(",") if n)
SERVICE_TYPES = ("_http._tcp", "_https._tcp", "_rtsp._tcp", "_onvif._tcp", "_workstation._tcp")


def _run(cmd, timeout=4):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout
    except Exception:
        return ""


def neighbors():
    out = []
    for line in _run(["ip", "neigh", "show"]).splitlines():
        m = re.match(r"(\S+)\s+dev\s+(\S+)(?:\s+lladdr\s+(\S+))?\s+(\S+)", line)
        if not m:
            continue
        ip, dev, mac, state = m.groups()
        out.append({"ip": ip, "dev": dev, "mac": (mac or "").upper(), "state": state, "source": "arp"})
    return out


def mdns():
    out = []
    text = _run(["avahi-browse", "-at", "-p", "-r"], timeout=5)
    for line in text.splitlines():
        if not line.startswith("="):
            continue
        f = line.split(";")
        if len(f) < 9:
            continue
        svc = f[4]
        if svc not in SERVICE_TYPES:
            continue
        name, host, addr, port = f[3], f[6], f[7], f[8]
        if not addr or addr.startswith("169.254."):
            continue
        out.append({"ip": addr, "dev": "", "mac": "", "name": name, "host": host,
                    "port": port, "service": svc, "source": "mdns"})
    return out


def in_zrt_subnet(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in ZRT_SUBNETS:
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False


def is_zrt(entry):
    """True for ATBM6461/MCU-fleet units (they get wake/sleep controls)."""
    mac = (entry.get("mac") or "").upper()
    return any(mac.startswith(p) for p in CAM_MAC_PREFIXES)


def looks_like_camera(entry):
    if is_zrt(entry):
        return True
    hay = " ".join(str(entry.get(k, "")) for k in ("name", "host")).lower()
    return any(h in hay for h in NAME_HINTS)


def candidates():
    merged = {}
    for e in neighbors() + mdns():
        ip = e.get("ip")
        if not ip:
            continue
        cur = merged.setdefault(ip, {"ip": ip, "mac": "", "name": "", "source": set()})
        cur["source"].add(e.get("source", "?"))
        if e.get("mac"):
            cur["mac"] = e["mac"]
        if e.get("name"):
            cur["name"] = e["name"]
    result = []
    for e in merged.values():
        e["source"] = ",".join(sorted(e["source"]))
        if looks_like_camera(e):
            result.append(e)
    return result
