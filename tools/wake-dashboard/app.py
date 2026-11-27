#!/usr/bin/env python3
"""ZRT wake dashboard — P0 implementation.

- HTTP UI/API on 0.0.0.0:8088
- MCU keepalive TCP listener on 0.0.0.0:12911 (MCU dials in; we capture frames)
- SQLite camera store
- Discovery via ip-neigh + avahi
- Wake API is wired but returns `unavailable` until the wake frame is reversed (P1)
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
import urllib3

import db
import discover
import wake

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
LOG_DIR = "/root/a1-work/logs/dashboard"
MCU_LOG_DIR = os.path.join(LOG_DIR, "mcu")
HTTP_PORT = int(os.environ.get("ZRT_HTTP_PORT", "8088"))
MCU_PORT = int(os.environ.get("ZRT_MCU_PORT", "12911"))
POLL_SECS = 10
DISCOVER_SECS = 300

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MCU_LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log")),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("zrt")

LOOP = None
STOP = None


class MCUConn:
    def __init__(self, ip, reader, writer):
        self.ip = ip
        self.reader = reader
        self.writer = writer
        self.connected_at = time.time()
        self.bytes = 0
        self._lock = asyncio.Lock()

    async def send(self, data):
        async with self._lock:
            self.writer.write(data)
            await self.writer.drain()

    async def send_wake(self, data, count=3, gap=1.0):
        """Burst like the cloud does: the MCU needs a few frames to take."""
        for i in range(count):
            await self.send(data)
            if i < count - 1:
                await asyncio.sleep(gap)


class MCUManager:
    def __init__(self):
        self.conns = {}

    def add(self, conn):
        old = self.conns.get(conn.ip)
        if old is not None:
            try:
                old.writer.close()
            except Exception:
                pass
        self.conns[conn.ip] = conn

    def remove(self, conn):
        if self.conns.get(conn.ip) is conn:
            del self.conns[conn.ip]

    def get(self, ip):
        return self.conns.get(ip)

    def snapshot(self):
        return {ip: {"connected_at": c.connected_at, "bytes": c.bytes} for ip, c in self.conns.items()}


MCU = MCUManager()


def have_device_id(buf):
    m = re.search(rb"[A-Z]{3}[A-Z0-9]{13}", buf)
    return m.group(0).decode() if m else None


async def handle_mcu(reader, writer):
    peer = writer.get_extra_info("peername") or ("?", 0)
    ip = peer[0]
    conn = MCUConn(ip, reader, writer)
    MCU.add(conn)
    log.info("MCU connect from %s", ip)
    db.upsert(ip, last_mcu_seen=time.time())

    start = time.strftime("%Y%m%d_%H%M%S")
    safe = ip.replace(":", "_")
    bin_path = os.path.join(MCU_LOG_DIR, f"{safe}_{start}.bin")
    hex_path = os.path.join(MCU_LOG_DIR, f"{safe}_{start}.hex")
    bf = open(bin_path, "ab")
    hf = open(hex_path, "a")
    seen = bytearray()
    try:
        while True:
            data = await asyncio.wait_for(reader.read(4096), timeout=3600)
            if not data:
                break
            conn.bytes += len(data)
            bf.write(data)
            bf.flush()
            hf.write(data.hex() + "\n")
            hf.flush()
            if len(seen) < 8192:
                seen.extend(data)
            did = have_device_id(seen)
            if did:
                db.upsert(ip, device_id=did)
    except asyncio.TimeoutError:
        log.info("MCU %s idle timeout", ip)
    except Exception as exc:
        log.info("MCU %s error: %s", ip, exc)
    finally:
        bf.close()
        hf.close()
        MCU.remove(conn)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        db.upsert(ip, last_mcu_seen=time.time())
        log.info("MCU disconnect %s (%d bytes)", ip, conn.bytes)


def probe(url):
    # A Session with an explicit close: a leaked probe socket (e.g. after a
    # read timeout) looks like an active viewer to the camera's pwrman.
    session = requests.Session()
    try:
        r = session.get(url, timeout=1.2, verify=False, allow_redirects=False,
                        headers={"Connection": "close"})
        if r.status_code < 500:
            return True, r.status_code
    except Exception:
        pass
    finally:
        session.close()
    return False, None


def probe_camera(cam):
    """Liveness by ICMP, not HTTP.

    The MCU owns the IP while the SoC is off and does not answer ping, so ping
    is a side-effect-free awake test. An HTTP probe would open a TCP connection
    on port 80/443 that the camera's pwrman counts as a viewer and would keep
    the camera awake forever.
    """
    ip = cam["ip"]
    ui = cam.get("ui_url") or f"http://{ip}/"
    try:
        rc = subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=3).returncode
        return rc == 0, ui, None
    except Exception:
        return False, ui, None


async def status_loop():
    while not STOP.is_set():
        cams = db.list_cameras()
        for cam in cams:
            try:
                ok, url, code = await asyncio.to_thread(probe_camera, cam)
                db.set_awake(cam["id"], ok, http_ok=ok, ui_url=(url if ok else None))
                if ok != bool(cam.get("awake")):
                    log.info("camera %s (%s) awake=%s status=%s", cam.get("name") or cam["ip"], cam["ip"], ok, code)
            except Exception as exc:
                log.info("probe %s failed: %s", cam["ip"], exc)
        await asyncio.sleep(POLL_SECS)


async def discover_loop():
    while not STOP.is_set():
        try:
            found = await asyncio.to_thread(discover.candidates)
            for e in found:
                ip = e["ip"]
                cur = db.by_ip(ip)
                if cur is None:
                    db.upsert(
                        ip,
                        mac=e.get("mac") or None,
                        name=e.get("name") or None,
                        ui_url=f"http://{ip}/",
                        notes=f"discovered via {e.get('source')}",
                    )
                    log.info("discovered %s %s", ip, e.get("name") or e.get("mac") or "")
                else:
                    upd = {}
                    if e.get("mac") and not cur.get("mac"):
                        upd["mac"] = e["mac"]
                    if e.get("name") and not cur.get("name"):
                        upd["name"] = e["name"]
                    if upd:
                        db.upsert(ip, **upd)
        except Exception as exc:
            log.info("discovery failed: %s", exc)
        await asyncio.sleep(DISCOVER_SECS)


def cam_public(cam):
    ip = cam["ip"]
    c = MCU.get(ip)
    mac = (cam.get("mac") or "").upper()
    is_zrt = mac.startswith("38:77:07") or bool(cam.get("device_id")) or c is not None
    return {
        "kind": "zrt" if is_zrt else "other",
        "id": cam["id"],
        "name": cam.get("name") or cam.get("device_id") or ip,
        "ip": ip,
        "mac": cam.get("mac"),
        "device_id": cam.get("device_id"),
        "device_mode": cam.get("device_mode"),
        "vendor_code": cam.get("vendor_code"),
        "model": cam.get("model"),
        "ui_url": cam.get("ui_url") or f"http://{ip}/",
        "awake": bool(cam.get("awake")),
        "mcu_connected": c is not None,
        "mcu_bytes": c.bytes if c else 0,
        "last_mcu_seen": cam.get("last_mcu_seen"),
        "last_http_ok": cam.get("last_http_ok"),
        "notes": cam.get("notes"),
    }


def json_bytes(obj, code=200):
    return code, json.dumps(obj).encode(), "application/json"


class Handler(BaseHTTPRequestHandler):
    server_version = "ZRTDash/0.1"

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code, body, ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        c, b, t = json_bytes(obj, code)
        self._send(c, b, t)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode() or "{}")
        except Exception:
            return {}

    def _cam_id(self, path, suffix):
        m = re.match(r"^/api/cameras/(\d+)/" + suffix + r"$", path)
        return int(m.group(1)) if m else None

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/api/health":
            return self._json({"ok": True, "mcu": MCU.snapshot(), "time": time.time()})
        if path == "/api/cameras":
            return self._json({"cameras": [cam_public(c) for c in db.list_cameras()]})
        m = re.match(r"^/api/cameras/(\d+)/status$", path)
        if m:
            cam = db.get(int(m.group(1)))
            if not cam:
                return self._json({"error": "not found"}, 404)
            ok, url, code = probe_camera(cam)
            db.set_awake(cam["id"], ok, http_ok=ok, ui_url=(url if ok else None))
            cam = db.get(cam["id"])
            out = cam_public(cam)
            out["http_code"] = code
            return self._json(out)
        m = re.match(r"^/c/(\d+)$", path)
        if m:
            cam = db.get(int(m.group(1)))
            if not cam:
                return self._send(404, b"no such camera", "text/plain")
            ok, url, _ = probe_camera(cam)
            db.set_awake(cam["id"], ok, http_ok=ok, ui_url=(url if ok else None))
            if ok and url:
                return self._send(302, b"", "text/plain", {"Location": url})
            return self._send(200, self._spinner(cam), "text/html; charset=utf-8")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/register":
            data = self._body()
            ip = data.get("ip")
            if not ip:
                return self._json({"error": "ip required"}, 400)
            fields = {k: data.get(k) for k in
                      ("name", "mac", "device_id", "device_mode", "vendor_code", "model", "ui_url")}
            fields = {k: v for k, v in fields.items() if v}
            cam = db.upsert(ip, **fields)
            log.info("register %s %s", ip, fields)
            return self._json(cam_public(cam))
        if path == "/api/cameras":
            data = self._body()
            ip = data.get("ip")
            if not ip:
                return self._json({"error": "ip required"}, 400)
            fields = {k: data.get(k) for k in
                      ("name", "mac", "device_id", "device_mode", "vendor_code", "model", "ui_url")}
            fields = {k: v for k, v in fields.items() if v}
            cam = db.upsert(ip, **fields)
            return self._json(cam_public(cam))
        m = re.match(r"^/api/cameras/(\d+)/wake$", path)
        if m:
            cam = db.get(int(m.group(1)))
            if not cam:
                return self._json({"result": "not_found"}, 404)
            ok, url, code = probe_camera(cam)
            db.set_awake(cam["id"], ok, http_ok=ok, ui_url=(url if ok else None))
            if ok:
                return self._json({"result": "awake", "ui_url": url or cam.get("ui_url")})
            conn = MCU.get(cam["ip"])
            if conn is None:
                return self._json({"result": "asleep_no_mcu",
                                   "reason": "no MCU keepalive connection to the dashboard"})
            frame = wake.build_wake_frame(cam)
            if not frame:
                return self._json({"result": "unavailable",
                                   "reason": "no wake frame for this camera"})
            try:
                fut = asyncio.run_coroutine_threadsafe(conn.send_wake(frame), LOOP)
                fut.result(timeout=10)
            except Exception as exc:
                return self._json({"result": "error", "reason": str(exc)}, 500)
            log.info("wake frame sent to %s (%d bytes x3)", cam["ip"], len(frame))
            return self._json({"result": "waking", "sent": len(frame), "burst": 3})
        m = re.match(r"^/api/cameras/(\d+)$", path)
        if m and self.command == "DELETE":
            db.delete(int(m.group(1)))
            return self._json({"ok": True})
        return self._send(404, b"not found", "text/plain")

    def do_DELETE(self):
        path = urlparse(self.path).path
        m = re.match(r"^/api/cameras/(\d+)$", path)
        if m:
            db.delete(int(m.group(1)))
            return self._json({"ok": True})
        return self._send(404, b"not found", "text/plain")

    def _static(self, rel):
        rel = rel.replace("\\", "/").lstrip("/")
        if ".." in rel.split("/"):
            return self._send(400, b"bad path", "text/plain")
        path = os.path.join(STATIC, rel)
        if not os.path.isfile(path):
            return self._send(404, b"not found", "text/plain")
        ext = os.path.splitext(path)[1].lower()
        ctype = {".html": "text/html; charset=utf-8",
                 ".js": "application/javascript",
                 ".css": "text/css",
                 ".svg": "image/svg+xml",
                 ".png": "image/png"}.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            body = f.read()
        return self._send(200, body, ctype)

    def _spinner(self, cam):
        ip = cam["ip"]
        ui = cam.get("ui_url") or f"http://{ip}/"
        cid = cam["id"]
        html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Waking {(cam.get('name') or ip)}</title>
<style>body{{background:#0f1420;color:#dbe4f0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center}}.spin{{width:42px;height:42px;border:4px solid #243049;border-top-color:#4f9cf9;border-radius:50%;margin:0 auto 18px;animation:r 1s linear infinite}}
@keyframes r{{to{{transform:rotate(360deg)}}}}a{{color:#4f9cf9}}</style></head><body><div class="box">
<div class="spin"></div><div id="m">Waking {ip} …</div>
<div id="s" style="margin-top:10px;color:#8a97ad;font-size:13px"></div>
</div><script>
const ui={json.dumps(ui)}; const id={cid};
async function tick(){{
 try{{const r=await fetch('/api/cameras/'+id+'/status',{{cache:'no-store'}});const j=await r.json();
  if(j.awake){{document.getElementById('m').textContent='Up — redirecting';window.location=ui;return;}}
  document.getElementById('s').textContent = j.mcu_connected ? 'MCU connected, waiting for SoC…' : 'MCU not connected';
 }}catch(e){{}}
 setTimeout(tick,1000);
}}
tick();
</script></body></html>"""
        return html.encode()


async def main_async():
    global LOOP, STOP
    LOOP = asyncio.get_running_loop()
    STOP = asyncio.Event()

    def _stop(*_):
        STOP.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            LOOP.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    db.init()
    log.info("starting: http=%d mcu=%d db=%s", HTTP_PORT, MCU_PORT, db.DB_PATH)

    mcu_server = await asyncio.start_server(handle_mcu, "0.0.0.0", MCU_PORT)
    log.info("MCU listener on 0.0.0.0:%d", MCU_PORT)

    httpd = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name="http", daemon=True).start()
    log.info("HTTP UI on 0.0.0.0:%d", HTTP_PORT)

    poll = asyncio.create_task(status_loop())
    disc = asyncio.create_task(discover_loop())

    await STOP.wait()
    log.info("stopping")
    poll.cancel()
    disc.cancel()
    httpd.shutdown()
    mcu_server.close()
    await mcu_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main_async())
