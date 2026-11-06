"""Jalankan: python -m tests.run_sim  -> tabel akurasi simulasi massal."""
import os
os.environ.pop("ANTHROPIC_API_KEY", None)
from app import engine
from app.parser import parse_message
from tests.sim_cases import ALL_CASES, CASES, HARD, T1


def got(text):
    cust = engine.find_customer(T1)
    parsed = parse_message(text)
    if not parsed.is_order:
        return "not_order"
    items = engine.build_items(cust, parsed)
    v = engine.validate(cust, items, parsed.unparsed)
    if any(i["status"] == "ambiguous" for i in items):
        return "ambiguous"
    if not items and parsed.unparsed:
        return "needs_review"
    return [(i.get("sku"), i["qty"], i.get("unit_final")) for i in items]


def score(cases, name):
    ok = 0
    for text, want in cases:
        g = got(text)
        ok += g == want
        if g != want:
            print(f"GAGAL  {text!r}\n   diharapkan: {want}\n   hasil     : {g}")
    print(f"{name}: {ok}/{len(cases)} = {ok/len(cases):.0%}")
    return ok == len(cases)


def main():
    a = score(CASES, "Set dasar (disetel)")
    b = score(HARD, "Set sulit (tidak disetel)")
    return a and b


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
