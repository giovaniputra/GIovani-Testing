"""Impor 'Product Master' (export TSV dari Excel hierarki produk) menjadi master.json aplikasi.

    python tools/import_master_tsv.py INPUT.tsv OUTPUT.json [--business Core] [--limit 120]

Kolom yang dibaca: Item, L2, L3, L6, L8 Code, Variant, Active?, Business Type, Inner Barcode.
File ini TIDAK memuat harga, isi dus, dan stok. Ketiganya dibiarkan kosong (null) dan perlu
dilengkapi dari sumber lain. Alias dibuat otomatis dari nama item dan varian.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def aliases_for(item: str, variant: str, l6: str, l3: str) -> list[str]:
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^\w\s.]", " ", s.lower())).strip()
    out = {norm(item), norm(f"{l6} {variant}"), norm(f"{l3} {variant}")}
    return sorted(a for a in out if a)


def load(path: str) -> list[dict]:
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    h = next(i for i, l in enumerate(lines) if l.startswith("Item\t"))
    hdr = lines[h].split("\t")
    rows = []
    for l in lines[h + 1:]:
        if not l.strip() or l.startswith("##"):
            continue
        p = l.split("\t")
        rows.append({k: (p[i] if i < len(p) else "").strip() for i, k in enumerate(hdr)})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--business", default="Core", help="Core / Non Core / Export (default Core)")
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--customers", default=str(Path(__file__).parent.parent / "data" / "master.json"))
    a = ap.parse_args()

    skus, seen = [], set()
    for r in load(a.src):
        if r.get("Active?") != "TRUE" or r.get("Business Type") != a.business or not r.get("L8 Code"):
            continue
        if r["L8 Code"] in seen:
            continue
        seen.add(r["L8 Code"])
        skus.append({
            "code": r["L8 Code"], "name": r["Item"], "category": r["L2"], "brand": r["L3"],
            "aliases": aliases_for(r["Item"], r["Variant"], r["L6"], r["L3"]),
            "units": {"pcs": 1}, "default_unit": "pcs",
            "price_pcs": None, "stock_pcs": None, "barcode": r.get("Inner Barcode") or None,
        })
        if len(skus) >= a.limit:
            break

    base = json.loads(Path(a.customers).read_text(encoding="utf-8"))
    customers = []
    for c in base["customers"]:  # toko dummy tetap dipakai; riwayat/alias/assortment dikosongkan (merujuk SKU lama)
        c = {k: v for k, v in c.items() if k not in ("usual_order", "history_avg_pcs", "aliases", "catalog_skus")}
        c.update(usual_order=[], history_avg_pcs={}, aliases={})
        customers.append(c)
    Path(a.dst).write_text(json.dumps({"_note": "Dari Product Master (tanpa harga/isi dus/stok). Jangan commit.",
                                       "skus": skus, "customers": customers}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"{len(skus)} SKU ditulis ke {a.dst}")


if __name__ == "__main__":
    main()
