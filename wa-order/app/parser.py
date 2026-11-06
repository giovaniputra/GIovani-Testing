"""Langkah 2 - Order Parser: teks chat bebas (Bahasa Indonesia) -> baris order terstruktur.

Parser berbasis aturan (tanpa API key, deterministik, bisa diuji). Bila ANTHROPIC_API_KEY
diset, ekstraksi dilakukan LLM lalu otomatis jatuh balik ke aturan jika gagal. Pencocokan
SKU/toko tetap dilakukan engine deterministik, LLM hanya mengekstrak.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

UNIT_MAP = {
    "dus": "dus", "karton": "dus", "ctn": "dus", "box": "dus", "kardus": "dus",
    "pcs": "pcs", "pc": "pcs", "biji": "pcs", "buah": "pcs", "btl": "pcs", "botol": "pcs",
    "pak": "pak", "pack": "pak", "bal": "bal", "lusin": "lusin", "lsn": "lusin",
    "renceng": "renceng", "rcg": "renceng",
}
UNIT_RE = "|".join(sorted(UNIT_MAP, key=len, reverse=True))
NUM_WORDS = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6,
             "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10}
MEASURE_RE = r"(?:ml|gr|gram|g|kg|l|liter|s)\b"

GREETING_RE = re.compile(
    r"^\s*(?:(?:halo|hai|hi|hallo|permisi|assalamualaikum|assalamu'alaikum|"
    r"selamat\s+(?:pagi|siang|sore|malam))\b[\s,!.]*)+", re.I)
VOCATIVE_RE = re.compile(r"^\s*(?:kak|kakak|pak|bu|bang|mas|mbak|min|om)\b[\s,!.]*", re.I)
FILLER = {"tolong", "mau", "order", "pesan", "pesen", "kirim", "kirimin", "ya", "yaa", "yah",
          "dong", "donk", "min", "kak", "kakak", "bu", "mohon", "minta", "nambah", "tambah",
          "sama", "juga", "lagi", "yg", "yang", "dari", "untuk", "buat", "nya", "aja", "saja", "tapi", "cuma"}
FRACTION = {"setengah", "separuh", "stengah", "1/2"}
IGNORABLE = {"terima", "kasih", "makasih", "thanks", "tq", "ok", "oke", "siap", "sip", "baik"}
REPEAT_RE = re.compile(r"\b(?:seperti|kayak|kaya|sama\s+kayak|sama\s+seperti|yang)?\s*"
                       r"(?:biasa|biasanya|kemarin|repeat)\b", re.I)
TRAIL_FILLER_RE = re.compile(r"(?:[\s,!.]+(?:ya|yaa|yah|dong|donk|kak|kakak|aja|saja|tolong|nya|min))+[\s,!.]*$", re.I)
# Beberapa item dalam satu kalimat tanpa pemisah: "2 hit lavender 1 stella gel", "hit lavender 2 dus stella gel 1 dus"
GLUE_UNIT_RE = re.compile(rf"([a-z.]\s+\d+\s*(?:{UNIT_RE})\b)\s+(?=[a-z])", re.I)
GLUE_BARE_RE = re.compile(rf"(?<=[a-z])\s+(?=\d+\s+(?!(?:{UNIT_RE}|{MEASURE_RE})\b)[a-z])", re.I)
SPLIT_RE = re.compile(r"[\n,;+&]|\s+(?:dan|sama|sm|trus|terus|lalu|sekalian)\s+", re.I)


@dataclass
class ParsedLine:
    raw: str
    qty: int
    unit: str | None
    product_text: str


@dataclass
class ParseResult:
    lines: list[ParsedLine] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    repeat_usual: bool = False
    order_like_unparsed: bool = False  # ada kalimat mirip order yang tidak bisa dibaca -> jangan diabaikan

    @property
    def is_order(self) -> bool:
        return bool(self.lines or self.repeat_usual or self.order_like_unparsed)


def _words_to_digits(text: str) -> str:
    pat = re.compile(rf"\b({'|'.join(NUM_WORDS)})\b(?=\s*(?:{UNIT_RE})\b)", re.I)
    return pat.sub(lambda m: str(NUM_WORDS[m.group(1).lower()]), text)


def _clean_product(text: str) -> str:
    text = re.sub(r"[^\w\s.]", " ", text.lower())
    tokens = [t for t in text.split() if t not in FILLER]
    return " ".join(tokens).strip()


_LEAD_RE = re.compile(rf"^(?:{'|'.join(sorted(FILLER, key=len, reverse=True))})\b[\s,]*", re.I)


def _strip_lead(seg: str) -> str:
    while (stripped := _LEAD_RE.sub("", seg, count=1)) != seg:
        seg = stripped
    return seg


def _split_glued(seg: str) -> list[str]:
    """Pecah item yang menempel dalam satu segmen, mis. '2 hit lavender 1 stella gel'."""
    seg = _strip_lead(seg.strip())
    if not re.match(r"\d", seg):  # gaya 'produk qty satuan produk qty satuan'
        seg = GLUE_UNIT_RE.sub(r"\1, ", seg)
    return [p for p in GLUE_BARE_RE.sub(", ", seg).split(", ") if p.strip()]


def _parse_segment(seg: str) -> ParsedLine | None:
    seg = seg.strip()
    seg = re.sub(r"(\d+)\s*x\b", r"\1", seg, flags=re.I)  # "2x hit" -> "2 hit"
    seg = re.sub(r"\bx\s*(\d+)\b", r" \1", seg, flags=re.I)  # "hit lavender x2" -> "hit lavender 2"
    seg = TRAIL_FILLER_RE.sub("", seg).strip()                 # "... 3 dus ya" -> "... 3 dus"
    lead = re.compile(rf"^(?:{'|'.join(sorted(FILLER, key=len, reverse=True))})\b[\s,]*", re.I)
    while (stripped := lead.sub("", seg, count=1)) != seg:  # "mau order 2 dus ..." -> "2 dus ..."
        seg = stripped
    # qty di depan: "2 dus hit lavender" / "3 hit lavender"
    m = re.match(rf"^(?P<qty>\d+)\s*(?:(?P<unit>{UNIT_RE})\b)?\s*(?P<prod>.+)$", seg, re.I)
    if m and not re.match(rf"^\d+\s*{MEASURE_RE}", seg, re.I):
        prod = _clean_product(m.group("prod"))
        if prod:
            unit = UNIT_MAP.get((m.group("unit") or "").lower())
            return ParsedLine(seg, int(m.group("qty")), unit, prod)
    # qty di belakang (wajib ada satuan): "hit lavender 2 dus"
    m = re.match(rf"^(?P<prod>.+?)\s+(?P<qty>\d+)\s*(?P<unit>{UNIT_RE})\b\.?$", seg, re.I)
    if m:
        prod = _clean_product(m.group("prod"))
        if prod:
            return ParsedLine(seg, int(m.group("qty")), UNIT_MAP[m.group("unit").lower()], prod)
    # qty di belakang tanpa satuan, 1-2 digit: "hit lavender 2" (satuan dilengkapi default SKU)
    m = re.match(r"^(?P<prod>.+?)\s+(?P<qty>\d{1,2})$", seg)
    if m:
        prod = _clean_product(m.group("prod"))
        if prod:
            return ParsedLine(seg, int(m.group("qty")), None, prod)
    return None


def parse_rules(text: str) -> ParseResult:
    res = ParseResult()
    text = GREETING_RE.sub("", text.strip())
    text = VOCATIVE_RE.sub("", text)
    text = _words_to_digits(text)
    segments = [piece for raw in SPLIT_RE.split(text) if raw and raw.strip()
                for piece in _split_glued(raw)]
    for seg in segments:
        if REPEAT_RE.search(seg):
            res.repeat_usual = True
            # "seperti kemarin tapi tambah stella gel 1 dus": sisa kalimat tetap dibaca
            rest = re.sub(r"^(?:tapi|cuma|hanya|tambah|plus|ditambah)\b[\s,]*", "",
                          REPEAT_RE.sub(" ", seg).strip(), flags=re.I)
            rest = re.sub(r"^(?:tapi|cuma|hanya|tambah|plus|ditambah)\b[\s,]*", "", rest, flags=re.I)
            extra = _parse_segment(rest) if rest.strip() else None
            if extra:
                res.lines.append(extra)
            continue
        line = _parse_segment(seg)
        if line:
            res.lines.append(line)
            continue
        tokens = [t for t in re.sub(r"[^\w\s]", " ", seg.lower()).split()
                  if t not in FILLER and t not in IGNORABLE]
        # Kalimat tanpa angka hanya dianggap sisa order jika sudah ada baris order lain
        if tokens and re.search(r"\d", seg):
            res.unparsed.append(seg.strip())
        # "setengah dus hit lavender": ada satuan/pecahan tapi tidak terbaca -> serahkan ke admin, jangan diam
        if tokens and set(tokens) & FRACTION:
            res.order_like_unparsed = True
            if seg.strip() not in res.unparsed:
                res.unparsed.append(seg.strip())
    return res


def parse_llm(text: str) -> ParseResult | None:
    """Ekstraksi via Claude (opsional). Mengembalikan None bila tidak aktif/gagal."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import httpx

        system = (
            "Kamu mengekstrak order dari chat WhatsApp toko ke salesman (Bahasa Indonesia, "
            "informal). Balas HANYA JSON: {\"repeat_usual\": bool, \"lines\": [{\"qty\": int, "
            "\"unit\": \"dus|pcs|pak|bal|lusin|renceng|null\", \"product\": str}], "
            "\"unparsed\": [str]}. repeat_usual=true jika toko minta 'seperti biasa/kemarin'. "
            "Jangan menebak SKU; salin nama produk sebagaimana ditulis. Abaikan sapaan."
        )
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
                  "max_tokens": 1024, "system": system,
                  "messages": [{"role": "user", "content": text}]},
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json()["content"][0]["text"]
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        res = ParseResult(repeat_usual=bool(data.get("repeat_usual")),
                          unparsed=[str(u) for u in data.get("unparsed", [])])
        for ln in data.get("lines", []):
            unit = UNIT_MAP.get(str(ln.get("unit") or "").lower())
            res.lines.append(ParsedLine(text, int(ln["qty"]), unit, _clean_product(str(ln["product"]))))
        return res
    except Exception:  # noqa: BLE001 - jatuh balik ke aturan
        return None


def parse_message(text: str) -> ParseResult:
    return parse_llm(text) or parse_rules(text)
