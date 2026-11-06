"""Penyimpanan SQLite: pesan masuk (idempotensi), order, dan outbox balasan."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = os.environ.get("WA_ORDER_DB", str(Path(__file__).parent.parent / "data" / "orders.db"))
PENDING = ("awaiting_confirmation", "awaiting_clarification")
PENDING_TTL_HOURS = 24


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS messages(wa_id TEXT PRIMARY KEY, phone TEXT, received_at TEXT);
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, updated_at TEXT,
            phone TEXT, customer_code TEXT, raw_text TEXT, items TEXT, issues TEXT,
            total REAL, confidence REAL, status TEXT);
        CREATE TABLE IF NOT EXISTS outbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, phone TEXT, body TEXT,
            order_id INTEGER, sent INTEGER DEFAULT 0, error TEXT);
        """)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def seen_message(wa_id: str | None, phone: str) -> bool:
    """True bila pesan sudah pernah diproses (WhatsApp mengirim ulang webhook saat timeout)."""
    if not wa_id:
        return False
    with _conn() as c:
        try:
            c.execute("INSERT INTO messages VALUES (?,?,?)", (wa_id, phone, now()))
            return False
        except sqlite3.IntegrityError:
            return True


def save_order(phone, customer_code, raw_text, items, issues, total, confidence, status) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO orders(created_at,updated_at,phone,customer_code,raw_text,items,issues,total,confidence,status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (now(), now(), phone, customer_code, raw_text, json.dumps(items), json.dumps(issues),
             total, confidence, status))
        return cur.lastrowid


def update_order(order_id: int, **fields) -> None:
    for k in ("items", "issues"):
        if k in fields:
            fields[k] = json.dumps(fields[k])
    fields["updated_at"] = now()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE orders SET {cols} WHERE id=?", (*fields.values(), order_id))


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["items"], d["issues"] = json.loads(d["items"]), json.loads(d["issues"])
    return d


def get_order(order_id: int) -> dict | None:
    with _conn() as c:
        return _row(c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def pending_order(phone: str) -> dict | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=PENDING_TTL_HOURS)).isoformat(timespec="seconds")
    q = ",".join("?" * len(PENDING))
    with _conn() as c:
        return _row(c.execute(
            f"SELECT * FROM orders WHERE phone=? AND status IN ({q}) AND updated_at>=? "
            "ORDER BY id DESC LIMIT 1", (phone, *PENDING, cutoff)).fetchone())


def list_orders(limit: int = 50) -> list[dict]:
    with _conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))]


def add_outbox(phone: str, body: str, order_id: int | None) -> int:
    with _conn() as c:
        return c.execute("INSERT INTO outbox(created_at,phone,body,order_id) VALUES (?,?,?,?)",
                         (now(), phone, body, order_id)).lastrowid


def mark_outbox(outbox_id: int, sent: bool, error: str | None = None) -> None:
    with _conn() as c:
        c.execute("UPDATE outbox SET sent=?, error=? WHERE id=?", (int(sent), error, outbox_id))


def list_outbox(phone: str | None = None, limit: int = 50) -> list[dict]:
    with _conn() as c:
        if phone:
            rows = c.execute("SELECT * FROM outbox WHERE phone=? ORDER BY id DESC LIMIT ?", (phone, limit))
        else:
            rows = c.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]
