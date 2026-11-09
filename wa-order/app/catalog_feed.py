"""Ekspor master data produk menjadi data feed katalog Meta (Commerce Manager).

    python -m app.catalog_feed --link https://contoh.co.id/produk --image https://contoh.co.id/img

Satu baris katalog = satu SKU dalam satuan default (mis. per dus). id feed = kode SKU, sehingga
`product_retailer_id` pada keranjang WhatsApp langsung identik dengan kode SKU di sistem.
Harga di katalog adalah harga list. Diskon/harga khusus per toko dihitung ulang oleh sistem saat order masuk.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .engine import load_master

COLUMNS = ["id", "title", "description", "availability", "condition", "price", "link",
           "image_link", "brand", "product_type"]


def feed_rows(link_base: str, image_base: str) -> list[dict]:
    rows = []
    for s in load_master()["skus"]:
        if s.get("price_pcs") is None:  # katalog Meta mewajibkan harga: produk tanpa harga dilewati
            continue
        unit = s["default_unit"]
        per = s["units"][unit]
        rows.append({
            "id": s["code"],
            "title": f"{s['name']} - per {unit}" + (f" (isi {per})" if per > 1 else ""),
            "description": f"{s['name']}, dijual per {unit}" + (f" isi {per} pcs." if per > 1 else "."),
            "availability": "out of stock" if (s.get("stock_pcs") is not None and s["stock_pcs"] < per) else "in stock",
            "condition": "new",
            "price": f"{s['price_pcs'] * per:.0f} IDR",
            "link": f"{link_base.rstrip('/')}/{s['code']}",
            "image_link": f"{image_base.rstrip('/')}/{s['code']}.jpg",
            "brand": s["name"].split()[0],
            "product_type": s.get("category", "Produk"),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", default="https://example.com/produk", help="URL dasar halaman produk")
    ap.add_argument("--image", default="https://example.com/img", help="URL dasar gambar produk (<kode>.jpg)")
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "catalog_feed.csv"))
    a = ap.parse_args()
    rows = feed_rows(a.link, a.image)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} produk ditulis ke {a.out}")


if __name__ == "__main__":
    main()
