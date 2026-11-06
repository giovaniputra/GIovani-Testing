"""Simulasi massal: chat gaya toko -> hasil yang diharapkan [(sku, qty, unit_final)] atau status khusus."""
H_LAV, H_ORG, H_REF = "HIT-AERO-LAV-600", "HIT-AERO-ORG-600", "HIT-ELEC-REF"
S_GEL, S_MAT, MITU, GNO, EXP = "STL-GEL-ORG", "STL-MATIC-REF", "MITU-WIPE-50", "GNO1-SOAP-100", "EXP-HC-HITAM"
T1 = "6281234567801"

# (pesan, diharapkan). diharapkan: list item, "ambiguous", "not_order", atau "needs_review"
CASES = [
    ("2 dus hit lavender", [(H_LAV, 2, "dus")]),
    ("hit lavender 2 dus", [(H_LAV, 2, "dus")]),
    ("kak, minta hit orange 3 dus ya", [(H_ORG, 3, "dus")]),
    ("Halo kak, mau order stella gel 2 dus", [(S_GEL, 2, "dus")]),
    ("pagi kak, stella matic 1 dus", [(S_MAT, 1, "dus")]),
    ("2dus hit lavender", [(H_LAV, 2, "dus")]),
    ("hit lavender 2dus", [(H_LAV, 2, "dus")]),
    ("2 krtn hit lavender", [(H_LAV, 2, "dus")]),
    ("2 ctn hit orange", [(H_ORG, 2, "dus")]),
    ("2 box mitu wipes", [(MITU, 2, "dus")]),
    ("dua dus hit lavender", [(H_LAV, 2, "dus")]),
    ("tiga karton stela gel", [(S_GEL, 3, "dus")]),
    ("2x hit lavender", [(H_LAV, 2, "dus")]),
    ("hit lavender x2", [(H_LAV, 2, "dus")]),
    ("hit lavender 2", [(H_LAV, 2, "dus")]),
    ("stella gel 3", [(S_GEL, 3, "dus")]),
    ("2 hit lavender 1 stella gel", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus")]),
    ("2 dus hit lavender sama 1 dus stella gel", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus")]),
    ("hit lavender 2 dus dan stella gel 1 dus", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus")]),
    ("hit lavender 2 dus, stella gel 1 dus, mitu wipes 1 pak", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus"), (MITU, 1, "pak")]),
    ("kak order:\n2 dus hit orange\n1 dus stella matic\n3 pak mitu wipes", [(H_ORG, 2, "dus"), (S_MAT, 1, "dus"), (MITU, 3, "pak")]),
    ("hit lavender 2 dus + mitu wipes 1 dus", [(H_LAV, 2, "dus"), (MITU, 1, "dus")]),
    ("tolong kirim 1 dus godrej no 1", [(GNO, 1, "dus")]),
    ("godrej no.1 3 pak", [(GNO, 3, "pak")]),
    ("sabun godrej 2 dus", [(GNO, 2, "dus")]),
    ("expert hitam 2 lusin", [(EXP, 2, "lusin")]),
    ("semir expert hitam 1 dus", [(EXP, 1, "dus")]),
    ("hit refill 2 pak", [(H_REF, 2, "pak")]),
    ("hit elektrik refill 1 dus", [(H_REF, 1, "dus")]),
    ("tisu basah mitu 2 dus", [(MITU, 2, "dus")]),
    ("1 dus mitu baby wipes 50s", [(MITU, 1, "dus")]),
    ("2 dus hit aerosol lavender 600 ml", [(H_LAV, 2, "dus")]),
    ("obat nyamuk 1 dus", [(H_LAV, 1, "dus")]),           # alias khusus toko TK-001
    ("sabun mandi 2 dus", [(GNO, 2, "dus")]),             # alias khusus toko TK-001
    ("seperti biasa ya kak", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus")]),
    ("yang biasa aja", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus")]),
    ("hit 2 dus", "ambiguous"),
    ("kak kapan barang sampai?", "not_order"),
    ("terima kasih kak", "not_order"),
    ("selamat pagi kak", "not_order"),
]

# Set uji lanjutan (sulit). Dibuat setelah parser disetel, tidak dipakai untuk menyetel.
HARD = [
    ("kak stok hit lavender masih ada? kirim 2 dus kalau ada", [(H_LAV, 2, "dus")]),
    ("hit lavender 2 dus, stella gel 1 dus, tambah mitu wipes 1 pak ya kak makasih", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus"), (MITU, 1, "pak")]),
    ("minta 1 karton mitu wipes sama 2 karton godrej no 1", [(MITU, 1, "dus"), (GNO, 2, "dus")]),
    ("hit lavendar 2 dus", [(H_LAV, 2, "dus")]),
    ("stela matik 1 dus", [(S_MAT, 1, "dus")]),
    ("setengah dus hit lavender", "needs_review"),
    # "orange" saja bisa HIT atau Stella, jadi bot bertanya ke toko
    ("hit lavender 2 dus tapi yang orange 1 dus", "ambiguous"),
    ("sama kayak kemarin tapi tambah stella gel 1 dus", [(H_LAV, 2, "dus"), (S_GEL, 1, "dus"), (S_GEL, 1, "dus")]),
    ("2 dus lavender", "ambiguous"),
    ("order ya", "not_order"),
    ("lusin expert hitam 3", [(EXP, 3, "lusin")]),
    ("kirim 12 pcs hit orange", [(H_ORG, 12, "pcs")]),
    ("hit lavender 24 pcs sama stella gel 24 pcs", [(H_LAV, 24, "pcs"), (S_GEL, 24, "pcs")]),
    ("pak andi, hit lavender 2 dus ya", [(H_LAV, 2, "dus")]),
]

ALL_CASES = CASES + HARD
