"""Langkah 4 - Konfirmasi balik ke toko di WhatsApp (nada chat biasa, bukan 'sistem').

Prinsip: hanya hal yang perlu dijawab toko yang ditanyakan. Isu internal (kredit, overdue,
stok, anomali) TIDAK pernah dibuka ke toko.
"""
from __future__ import annotations

import os

import httpx

from . import store
from .engine import load_master


def rp(n: float) -> str:
    return "Rp" + f"{n:,.0f}".replace(",", ".")


def _qty_text(it: dict) -> str:
    unit = it.get("unit_final") or it.get("unit") or ""
    pcs = it.get("qty_pcs")
    extra = f" ({pcs} pcs)" if pcs and unit != "pcs" else ""
    return f"{it['qty']} {unit}{extra}".strip()


def summary_text(customer: dict, items: list[dict], total: float) -> str:
    lines = [f"{i}. {it['name']} - {_qty_text(it)}" for i, it in enumerate(items, 1)]
    return (
        f"Halo Kak {customer['name']} 🙏 Pesanannya kami catat ya:\n" + "\n".join(lines) +
        f"\n\nEstimasi total {rp(total)}.\nBalas *OK* kalau sudah benar, atau balas *ubah* kalau ada yang salah."
    )


def clarification_text(customer: dict, items: list[dict]) -> str:
    it = next(i for i in items if i["status"] == "ambiguous")
    master = load_master()["sku_by_code"]
    opts = "\n".join(f"{n}. {master[c]['name']}" for n, c in enumerate(it["candidates"], 1))
    return (f"Halo Kak {customer['name']} 🙏 Untuk \"{it['product_text']}\", maksudnya yang mana ya?\n"
            f"{opts}\nBalas dengan nomornya saja ya Kak.")


def received_text(customer: dict | None) -> str:
    who = f" Kak {customer['name']}" if customer else ""
    return f"Halo{who} 🙏 Pesanannya sudah kami terima, tim kami proses dan konfirmasi segera ya."


def unknown_text() -> str:
    return "Halo 🙏 Pesan Kakak sudah kami terima dan diteruskan ke tim sales kami."


def confirmed_text(customer: dict, order_id: int) -> str:
    return f"Siap Kak {customer['name']}, pesanan #{order_id} sudah terkonfirmasi ✅ Terima kasih!"


def retry_text() -> str:
    return "Baik Kak, mohon tulis ulang pesanan yang benar ya, nanti kami catat lagi 🙏"


def cancelled_text(order_id: int) -> str:
    return f"Baik Kak, pesanan #{order_id} kami batalkan."


def send(phone: str, body: str, order_id: int | None = None) -> int:
    """Catat ke outbox lalu kirim via WhatsApp Cloud API (bila kredensial diset)."""
    oid = store.add_outbox(phone, body, order_id)
    token, phone_id = os.environ.get("WHATSAPP_TOKEN"), os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not (token and phone_id):
        return oid  # mode simulasi: hanya tersimpan di outbox
    try:
        r = httpx.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"messaging_product": "whatsapp", "to": phone, "type": "text",
                  "text": {"body": body}},
            timeout=15,
        )
        r.raise_for_status()
        store.mark_outbox(oid, True)
    except Exception as e:  # noqa: BLE001
        store.mark_outbox(oid, False, str(e)[:300])
    return oid
