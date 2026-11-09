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
    total_line = f"\n\nEstimasi total {rp(total)}." if all(it.get("subtotal") is not None for it in items) else ""
    return (
        f"Halo Kak {customer['name']} 🙏 Pesanannya kami catat ya:\n" + "\n".join(lines) + total_line +
        "\nBalas *OK* kalau sudah benar, atau balas *ubah* kalau ada yang salah."
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


def _deliver(oid: int, payload: dict) -> None:
    """Kirim ke WhatsApp Cloud API bila kredensial diset. Tanpa kredensial: hanya tersimpan di outbox (simulasi)."""
    token, phone_id = os.environ.get("WHATSAPP_TOKEN"), os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not (token and phone_id):
        return
    try:
        r = httpx.post(f"https://graph.facebook.com/v21.0/{phone_id}/messages",
                       headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=15)
        r.raise_for_status()
        store.mark_outbox(oid, True)
    except Exception as e:  # noqa: BLE001
        store.mark_outbox(oid, False, str(e)[:300])


def send(phone: str, body: str, order_id: int | None = None) -> int:
    """Pesan teks biasa."""
    oid = store.add_outbox(phone, body, order_id)
    _deliver(oid, {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": body}})
    return oid


# ---- Katalog resmi WhatsApp (multi-product message) ----
MAX_ITEMS, MAX_SECTIONS = 30, 10  # batas WhatsApp untuk product_list


def catalog_sections(customer: dict | None) -> list[dict]:
    from .engine import allowed_skus
    groups: dict[str, list[str]] = {}
    for s in allowed_skus(customer):
        groups.setdefault(s.get("category", "Produk"), []).append(s["code"])
    sections, n = [], 0
    for title, codes in list(groups.items())[:MAX_SECTIONS]:
        codes = codes[: MAX_ITEMS - n]
        if not codes:
            break
        n += len(codes)
        sections.append({"title": title[:24], "product_items": [{"product_retailer_id": c} for c in codes]})
    return sections


def catalog_payload(phone: str, customer: dict) -> dict:
    return {
        "messaging_product": "whatsapp", "to": phone, "type": "interactive",
        "interactive": {
            "type": "product_list",
            "header": {"type": "text", "text": "Katalog Produk"},
            "body": {"text": f"Halo Kak {customer['name']} 🙏 Silakan pilih produk dan jumlahnya, lalu kirim keranjangnya ya."},
            "footer": {"text": "Harga mengikuti harga toko Kakak"},
            "action": {"catalog_id": os.environ.get("WHATSAPP_CATALOG_ID", ""),
                       "sections": catalog_sections(customer)},
        },
    }


def catalog_text(customer: dict) -> str:
    skus = load_master()["sku_by_code"]
    lines = []
    for sec in catalog_sections(customer):
        lines.append(f"*{sec['title']}*")
        lines += [f"- {skus[i['product_retailer_id']]['name']}" for i in sec["product_items"]]
    return (f"Halo Kak {customer['name']} 🙏 Ini daftar produk kami:\n" + "\n".join(lines) +
            "\n\nBalas dengan nama produk dan jumlahnya ya Kak.")


def send_catalog(phone: str, customer: dict, order_id: int | None = None) -> tuple[int, str]:
    """Kirim katalog. Bila WhatsApp belum terhubung ke katalog (WHATSAPP_CATALOG_ID kosong) saat
    kredensial aktif, jatuh balik ke daftar teks supaya toko tetap terlayani."""
    live = bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))
    if live and not os.environ.get("WHATSAPP_CATALOG_ID"):
        text = catalog_text(customer)
        return send(phone, text, order_id), text
    payload = catalog_payload(phone, customer)
    preview = "[Katalog produk dikirim]\n" + catalog_text(customer).split("\n\n")[0].split("\n", 1)[1]
    oid = store.add_outbox(phone, preview, order_id, payload)
    _deliver(oid, payload)
    return oid, preview
