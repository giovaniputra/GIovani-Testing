"""Langkah 3 - Matching & validasi: kenali toko, petakan alias SKU, cek stok/kredit/anomali."""
from __future__ import annotations

import difflib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .parser import ParseResult

MASTER_PATH = Path(os.environ.get("WA_MASTER", Path(__file__).parent.parent / "data" / "master.json"))
MATCH_OK, MATCH_MARGIN, MATCH_MIN = 0.85, 0.10, 0.55
ANOMALY_X = 5          # qty > 5x rata-rata histori toko -> tandai
OVERDUE_DAYS = 30


@lru_cache(maxsize=1)
def load_master() -> dict:
    data = json.loads(MASTER_PATH.read_text(encoding="utf-8"))
    data["sku_by_code"] = {s["code"]: s for s in data["skus"]}
    return data


def norm_phone(p: str) -> str:
    d = re.sub(r"\D", "", p or "")
    if d.startswith("0"):
        d = "62" + d[1:]
    elif d.startswith("8"):
        d = "62" + d
    return d


def find_customer(phone: str) -> dict | None:
    p = norm_phone(phone)
    return next((c for c in load_master()["customers"] if p in map(norm_phone, c["phones"])), None)


def _tokens(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", s.lower().replace(".", "")).split()


def _score(prod: str, alias: str) -> float:
    p, a = _tokens(prod), _tokens(alias)
    if not p or not a:
        return 0.0
    ps, as_ = set(p), set(a)
    if as_ <= ps:                                  # semua kata alias ada di teks toko
        s = 0.85 + 0.15 * len(as_) / len(ps)
    elif ps <= as_:                                # teks toko lebih umum dari alias
        s = 0.5 + 0.4 * len(ps) / len(as_)
    else:
        s = 0.0
    return max(s, difflib.SequenceMatcher(None, " ".join(p), " ".join(a)).ratio())


def match_sku(product_text: str, customer: dict | None) -> dict:
    """Hasil: status matched | ambiguous | unmatched, plus kandidat."""
    master = load_master()
    if customer:  # alias khusus toko didahulukan ("obat nyamuk" -> HIT ...)
        for alias, code in customer.get("aliases", {}).items():
            if _tokens(alias) == _tokens(product_text):
                return {"status": "matched", "sku": code, "score": 1.0, "candidates": []}
    scored: dict[str, float] = {}
    for sku in master["skus"]:
        best = max(_score(product_text, a) for a in sku["aliases"] + [sku["name"]])
        if best >= MATCH_MIN:
            scored[sku["code"]] = best
    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return {"status": "unmatched", "sku": None, "score": 0.0, "candidates": []}
    top, second = ranked[0], ranked[1] if len(ranked) > 1 else (None, 0.0)
    if top[1] >= MATCH_OK and top[1] - second[1] >= MATCH_MARGIN:
        return {"status": "matched", "sku": top[0], "score": round(top[1], 2), "candidates": []}
    return {"status": "ambiguous", "sku": None, "score": round(top[1], 2),
            "candidates": [c for c, _ in ranked[:3]]}


def build_items(customer: dict | None, parsed: ParseResult) -> list[dict]:
    items: list[dict] = []
    if parsed.repeat_usual and customer:
        for u in customer.get("usual_order", []):
            items.append({"raw": "(order seperti biasa)", "qty": u["qty"], "unit": u["unit"],
                          "product_text": load_master()["sku_by_code"][u["sku"]]["name"],
                          "status": "matched", "sku": u["sku"], "score": 1.0, "candidates": [],
                          "source": "usual"})
    for ln in parsed.lines:
        m = match_sku(ln.product_text, customer)
        items.append({"raw": ln.raw, "qty": ln.qty, "unit": ln.unit, "product_text": ln.product_text,
                      **m, "source": "chat"})
    return items


def validate(customer: dict | None, items: list[dict], unparsed: list[str] | None = None) -> dict:
    """Isi detail baris (satuan, pcs, harga) dan kumpulkan issues.

    severity: 'ask' = perlu ditanyakan ke toko, 'internal' = ditangani tim (tidak dibuka ke toko).
    """
    master = load_master()
    issues: list[dict] = []
    total = 0.0
    for text in unparsed or []:
        issues.append({"code": "unparsed", "severity": "internal", "message": f"Tidak terbaca: '{text}'"})
    if customer is None:
        issues.append({"code": "unknown_customer", "severity": "internal",
                       "message": "Nomor WA belum terdaftar di master customer"})
    if not items:
        issues.append({"code": "no_items", "severity": "internal", "message": "Tidak ada item order"})
    for it in items:
        if it["status"] == "unmatched":
            issues.append({"code": "unmatched", "severity": "internal",
                           "message": f"Produk tidak dikenali: '{it['product_text']}'"})
            continue
        if it["status"] == "ambiguous":
            issues.append({"code": "ambiguous", "severity": "ask",
                           "message": f"Produk ambigu: '{it['product_text']}'"})
            continue
        sku = master["sku_by_code"][it["sku"]]
        it["name"] = sku["name"]
        unit = it["unit"] or sku["default_unit"]
        if not it["unit"]:
            issues.append({"code": "unit_assumed", "severity": "info",
                           "message": f"{sku['name']}: satuan tidak disebut, diasumsikan {unit}"})
        if unit not in sku["units"]:
            issues.append({"code": "bad_unit", "severity": "internal",
                           "message": f"{sku['name']}: satuan '{unit}' tidak tersedia"})
            it["unit_final"], it["qty_pcs"] = unit, None
            continue
        it["unit_final"] = unit
        it["qty_pcs"] = it["qty"] * sku["units"][unit]
        disc = (customer or {}).get("discount_pct", 0)
        it["unit_price"] = round(sku["price_pcs"] * sku["units"][unit] * (1 - disc / 100))
        it["subtotal"] = it["unit_price"] * it["qty"]
        total += it["subtotal"]
        if it["qty"] <= 0:
            issues.append({"code": "bad_qty", "severity": "internal", "message": f"{sku['name']}: qty tidak valid"})
        if it["qty_pcs"] > sku["stock_pcs"]:
            issues.append({"code": "low_stock", "severity": "internal",
                           "message": f"{sku['name']}: diminta {it['qty_pcs']} pcs, stok {sku['stock_pcs']} pcs"})
        avg = (customer or {}).get("history_avg_pcs", {}).get(it["sku"])
        if avg and it["qty_pcs"] > ANOMALY_X * avg:
            issues.append({"code": "qty_anomaly", "severity": "internal",
                           "message": f"{sku['name']}: {it['qty_pcs']} pcs > {ANOMALY_X}x rata-rata toko ({avg} pcs)"})
    if customer:
        if customer.get("overdue_days", 0) > OVERDUE_DAYS:
            issues.append({"code": "overdue", "severity": "internal",
                           "message": f"Toko overdue {customer['overdue_days']} hari"})
        if customer["outstanding"] + total > customer["credit_limit"]:
            issues.append({"code": "credit_limit", "severity": "internal",
                           "message": f"Piutang {customer['outstanding']:,.0f} + order {total:,.0f} melebihi limit {customer['credit_limit']:,.0f}"})
    scores = [it["score"] for it in items if it.get("sku")]
    return {"issues": issues, "total": total, "confidence": round(min(scores), 2) if scores else 0.0}


def decide_status(items: list[dict], issues: list[dict]) -> str:
    blocking = [i for i in issues if i["severity"] in ("ask", "internal")]
    asks = [i for i in blocking if i["severity"] == "ask"]
    if not blocking:
        return "awaiting_confirmation"
    if len(asks) == 1 and len(blocking) == 1:
        return "awaiting_clarification"
    return "needs_review"
