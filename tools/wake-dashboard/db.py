import os
import sqlite3
import threading
import time
from contextlib import closing

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "cameras.db")

_lock = threading.Lock()

ALLOWED = {
    "name", "mac", "device_id", "device_mode", "vendor_code",
    "ui_url", "model", "notes", "awake", "last_mcu_seen", "last_http_ok",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL UNIQUE,
    name TEXT,
    mac TEXT,
    device_id TEXT,
    device_mode TEXT,
    vendor_code TEXT,
    ui_url TEXT,
    model TEXT,
    awake INTEGER NOT NULL DEFAULT 0,
    last_mcu_seen REAL,
    last_http_ok REAL,
    notes TEXT,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cameras_mac ON cameras(mac);
CREATE INDEX IF NOT EXISTS idx_cameras_did ON cameras(device_id);
"""


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, closing(_conn()) as c:
        c.executescript(SCHEMA)
        c.commit()


def _row(r):
    return dict(r) if r is not None else None


def list_cameras():
    with _lock, closing(_conn()) as c:
        return [_row(r) for r in c.execute("SELECT * FROM cameras ORDER BY name, ip")]


def get(cam_id):
    with _lock, closing(_conn()) as c:
        return _row(c.execute("SELECT * FROM cameras WHERE id=?", (cam_id,)).fetchone())


def by_ip(ip):
    with _lock, closing(_conn()) as c:
        return _row(c.execute("SELECT * FROM cameras WHERE ip=?", (ip,)).fetchone())


def upsert(ip, **fields):
    fields = {k: v for k, v in fields.items() if k in ALLOWED and v is not None}
    now = time.time()
    with _lock, closing(_conn()) as c:
        row = c.execute("SELECT * FROM cameras WHERE ip=?", (ip,)).fetchone()
        if row:
            if fields:
                sets = ", ".join(f"{k}=?" for k in fields)
                vals = list(fields.values()) + [now, row["id"]]
                c.execute(f"UPDATE cameras SET {sets}, updated=? WHERE id=?", vals)
        else:
            cols = ["ip", "created", "updated"] + list(fields)
            vals = [ip, now, now] + list(fields.values())
            c.execute(
                f"INSERT INTO cameras ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                vals,
            )
        c.commit()
        return _row(c.execute("SELECT * FROM cameras WHERE ip=?", (ip,)).fetchone())


def set_mcu(ip, connected, ts=None):
    ts = time.time() if ts is None else ts
    return upsert(ip, last_mcu_seen=ts)


def set_awake(cam_id, awake, http_ok=None, ui_url=None):
    now = time.time()
    with _lock, closing(_conn()) as c:
        if ui_url:
            c.execute(
                "UPDATE cameras SET awake=?, last_http_ok=?, ui_url=?, updated=? WHERE id=?",
                (1 if awake else 0, now if http_ok else None, ui_url, now, cam_id),
            )
        elif http_ok:
            c.execute(
                "UPDATE cameras SET awake=?, last_http_ok=?, updated=? WHERE id=?",
                (1 if awake else 0, now, now, cam_id),
            )
        else:
            c.execute(
                "UPDATE cameras SET awake=?, updated=? WHERE id=?",
                (1 if awake else 0, now, cam_id),
            )
        c.commit()


def delete(cam_id):
    with _lock, closing(_conn()) as c:
        c.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
        c.commit()
