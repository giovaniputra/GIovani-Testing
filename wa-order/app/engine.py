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
    demo = os.environ.get("DEMO_PHONE")  # nomor WA tester -> dipetakan ke toko demo, tanpa menyimpannya di repo
    if demo:
        code = os.environ.get("DEMO_CUSTOMER", "TK-001")
        for c in data["customers"]:
            if c["code"] == code:
                c["phones"] = c["phones"] + [p.strip() for p in demo.split(",") if p.strip()]
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
    t = re.sub(r"[^\w\s]", " ", s.lower().replace(".", ""))
    return re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", t).split()


def _score(prod: str, alias: str) -> tuple[float, frozenset]:
    """Skor 0-1 dan himpunan kata alias yang dipakai (untuk aturan dominasi)."""
    p, a = _tokens(prod), _tokens(alias)
    if not p or not a:
        return 0.0, frozenset()
    ps, as_ = set(p), set(a)
    if as_ <= ps:                                  # semua kata alias ada di teks toko
        s = 0.85 + 0.15 * len(as_) / len(ps)
    elif ps <= as_:                                # teks toko lebih umum dari alias
        s = 0.5 + 0.4 * len(ps) / len(as_)
    else:
        s = 0.0
    name_match = s > 0                             # nama cocok lewat kata, bukan sekadar mirip huruf
    s = max(s, difflib.SequenceMatcher(None, " ".join(p), " ".join(a)).ratio())
    np_, na = {t for t in ps if t.isdigit()}, {t for t in as_ if t.isdigit()}
    if np_ and na:                                 # ukuran/isi disebut: beda = penalti, cocok = bonus (hanya jika nama cocok)
        if not np_ & na:
            s -= 0.25
        elif name_match:
            s = min(1.0, s + 0.15)
    return s, frozenset(as_)


def _apply_synonyms(text: str) -> str:
    t = " ".join(_tokens(text))
    for phrase, repl in load_master().get("synonyms", {}).items():
        ph = " ".join(_tokens(phrase))
        if ph and re.search(rf"(?<!\w){re.escape(ph)}(?!\w)", t):
            t = re.sub(rf"(?<!\w){re.escape(ph)}(?!\w)", " ".join(_tokens(repl)), t)
    return re.sub(r"\s+", " ", t).strip()


def match_sku(product_text: str, customer: dict | None) -> dict:
    """Hasil: status matched | ambiguous | unmatched, plus kandidat."""
    master = load_master()
    if customer:  # alias khusus toko didahulukan ("obat nyamuk" -> HIT ...)
        for alias, code in customer.get("aliases", {}).items():
            if _tokens(alias) == _tokens(product_text):
                return {"status": "matched", "sku": code, "score": 1.0, "candidates": []}
    product_text = _apply_synonyms(product_text)  # istilah sehari-hari ("lem tikus") -> nama produk
    scored: dict[str, tuple[float, frozenset]] = {}
    for sku in master["skus"]:
        best = max((_score(product_text, a) for a in sku["aliases"] + [sku["name"]]), key=lambda x: x[0])
        if best[0] >= MATCH_MIN:
            scored[sku["code"]] = best
    ranked = sorted(scored.items(), key=lambda kv: kv[1][0], reverse=True)
    if not ranked:
        return {"status": "unmatched", "sku": None, "score": 0.0, "candidates": []}
    (top_code, (top, top_tok)) = ranked[0]
    second, second_tok = (ranked[1][1] if len(ranked) > 1 else (0.0, frozenset()))
    clear = top - second >= MATCH_MARGIN or (top_tok > second_tok and top - second > 0)  # alias lebih spesifik menang
    if (top >= MATCH_OK and clear) or (len(ranked) == 1 and top >= 0.6):  # satu-satunya kandidat; toko tetap melihat nama lengkap di konfirmasi
        return {"status": "matched", "sku": top_code, "score": round(top, 2), "candidates": []}
    return {"status": "ambiguous", "sku": None, "score": round(top, 2),
            "candidates": [c for c, _ in ranked[:3]]}


def allowed_skus(customer: dict | None) -> list[dict]:
    """Produk yang boleh dibeli/ditampilkan untuk toko (assortment). Kosong = semua produk."""
    codes = (customer or {}).get("catalog_skus")
    return [s for s in load_master()["skus"] if not codes or s["code"] in codes]


def build_items_from_cart(customer: dict | None, product_items: list[dict]) -> list[dict]:
    """Keranjang katalog WhatsApp -> item order. product_retailer_id = kode SKU, atau 'SKU:satuan'."""
    skus = load_master()["sku_by_code"]
    items: list[dict] = []
    for p in product_items:
        rid = str(p.get("product_retailer_id", "")).strip()
        code, _, unit = rid.partition(":")
        try:
            qty = int(p.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0
        sku = skus.get(code)
        base = {"raw": f"[keranjang] {rid}", "qty": qty, "source": "cart", "candidates": []}
        if sku is None:
            items.append({**base, "unit": None, "product_text": rid, "status": "unmatched", "sku": None, "score": 0.0})
        else:
            items.append({**base, "unit": unit or sku["default_unit"], "product_text": sku["name"],
                          "status": "matched", "sku": code, "score": 1.0})
    return items


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
        allowed = (customer or {}).get("catalog_skus")
        if allowed and it["sku"] not in allowed:
            issues.append({"code": "not_in_assortment", "severity": "internal",
                           "message": f"{sku['name']}: bukan produk yang tersedia untuk toko ini"})
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
        if sku.get("price_pcs") is None:  # master belum punya harga: total tidak dihitung
            it["unit_price"] = it["subtotal"] = None
            issues.append({"code": "price_missing", "severity": "info",
                           "message": f"{sku['name']}: harga belum ada di master"})
        else:
            it["unit_price"] = round(sku["price_pcs"] * sku["units"][unit] * (1 - disc / 100))
            it["subtotal"] = it["unit_price"] * it["qty"]
            total += it["subtotal"]
        if it["qty"] <= 0:
            issues.append({"code": "bad_qty", "severity": "internal", "message": f"{sku['name']}: qty tidak valid"})
        if sku.get("stock_pcs") is not None and it["qty_pcs"] > sku["stock_pcs"]:
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
