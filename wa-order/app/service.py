"""Orkestrasi: pesan masuk -> parse -> match/validasi -> balasan konfirmasi."""
from __future__ import annotations

import re

from . import engine, replier, store
from .parser import parse_message

CONFIRM = {"ok", "oke", "okey", "ya", "iya", "yes", "betul", "benar", "sip", "siap", "setuju", "lanjut"}
CHANGE = {"ubah", "salah", "revisi", "ganti", "tidak", "gak", "nggak"}
CANCEL = {"batal", "cancel", "batalkan"}
CATALOG_RE = re.compile(r"\b(katalog|catalog|daftar produk|list produk)\b", re.I)


def _word(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _finalize(order_id: int, phone: str, customer: dict | None, items: list[dict],
              unparsed: list[str] | None, raw_text: str | None = None) -> dict:
    v = engine.validate(customer, items, unparsed)
    status = engine.decide_status(items, v["issues"])
    fields = dict(items=items, issues=v["issues"], total=v["total"], confidence=v["confidence"], status=status)
    if order_id:
        store.update_order(order_id, **fields)
    else:
        order_id = store.save_order(phone, customer["code"] if customer else None, raw_text,
                                    items, v["issues"], v["total"], v["confidence"], status)
    if customer is None:
        reply = replier.unknown_text()
    elif status == "awaiting_confirmation":
        reply = replier.summary_text(customer, items, v["total"])
    elif status == "awaiting_clarification":
        reply = replier.clarification_text(customer, items)
    else:
        reply = replier.received_text(customer)
    replier.send(phone, reply, order_id)
    return {"order_id": order_id, "status": status, "reply": reply, "issues": v["issues"], "total": v["total"]}


def handle_incoming(phone: str, text: str | None, wa_id: str | None = None,
                    msg_type: str = "text", order: dict | None = None) -> dict:
    phone = engine.norm_phone(phone)
    if store.seen_message(wa_id, phone):
        return {"status": "duplicate"}
    customer = engine.find_customer(phone)

    if msg_type == "order":  # keranjang dari katalog WhatsApp: sudah terstruktur, tanpa parsing teks
        pending = store.pending_order(phone)
        if pending:
            store.update_order(pending["id"], status="superseded")
        items = engine.build_items_from_cart(customer, (order or {}).get("product_items", []))
        return _finalize(0, phone, customer, items, None, raw_text=f"[keranjang katalog] {len(items)} item")

    if msg_type != "text" or not text:  # voice note / foto: belum diproses otomatis -> tim
        oid = store.save_order(phone, customer["code"] if customer else None, f"[{msg_type}]",
                               [], [{"code": "media", "severity": "internal",
                                     "message": f"Pesan {msg_type} perlu dibaca manual"}], 0, 0, "needs_review")
        reply = replier.received_text(customer)
        replier.send(phone, reply, oid)
        return {"order_id": oid, "status": "needs_review", "reply": reply}

    if CATALOG_RE.search(text) and not parse_message(text).lines:  # "katalog" / "minta daftar produk"
        if customer is None:
            reply = replier.unknown_text()
            replier.send(phone, reply)
            return {"status": "unknown_customer", "reply": reply}
        _, preview = replier.send_catalog(phone, customer)
        return {"status": "catalog_sent", "reply": preview}

    pending = store.pending_order(phone)
    word = _word(text)
    if pending and customer:
        if word in CONFIRM and pending["status"] == "awaiting_confirmation":
            store.update_order(pending["id"], status="confirmed")
            reply = replier.confirmed_text(customer, pending["id"])
            replier.send(phone, reply, pending["id"])
            return {"order_id": pending["id"], "status": "confirmed", "reply": reply}
        if word in CANCEL:
            store.update_order(pending["id"], status="cancelled")
            reply = replier.cancelled_text(pending["id"])
            replier.send(phone, reply, pending["id"])
            return {"order_id": pending["id"], "status": "cancelled", "reply": reply}
        if word in CHANGE:
            store.update_order(pending["id"], status="superseded")
            reply = replier.retry_text()
            replier.send(phone, reply, pending["id"])
            return {"order_id": pending["id"], "status": "superseded", "reply": reply}
        if pending["status"] == "awaiting_clarification" and word.isdigit():
            amb = next((i for i in pending["items"] if i["status"] == "ambiguous"), None)
            idx = int(word) - 1
            if amb and 0 <= idx < len(amb["candidates"]):
                amb.update(status="matched", sku=amb["candidates"][idx], score=1.0, candidates=[])
                return _finalize(pending["id"], phone, customer, pending["items"], None)

    parsed = parse_message(text)
    if not parsed.is_order:  # obrolan biasa -> biarkan salesman, bot tidak ikut campur
        return {"status": "not_order"}
    if pending:
        store.update_order(pending["id"], status="superseded")
    items = engine.build_items(customer, parsed)
    return _finalize(0, phone, customer, items, parsed.unparsed, raw_text=text)
