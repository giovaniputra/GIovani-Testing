#!/usr/bin/env python3
"""Ambil semua Kurs Transaksi BI dari bi.go.id dan simpan ke CSV.

Hanya memakai library bawaan Python 3.8+ (tidak perlu pip install).

Contoh:
  python ambil_kurs.py                              # kurs terbaru, semua mata uang
  python ambil_kurs.py --dari 2026-10-01            # 1 Okt 2026 s/d kurs terbaru
  python ambil_kurs.py --dari 2026-10-01 --sampai 2026-10-31
  python ambil_kurs.py --mata-uang USD EUR JPY      # hanya mata uang tertentu
  python ambil_kurs.py --output kurs_oktober.csv
"""
import argparse, csv, html, http.cookiejar, re, sys, time, urllib.parse, urllib.request
from datetime import date, datetime, timedelta

URL = "https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx"
P = "ctl00$ctl51$g_6c89d4ad_107f_437d_bd54_8fda17b556bf$ctl00$"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
BULAN = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
         "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12}


def buka(data=None, retry=3):
    jar = buka.jar
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(URL, data=data, headers={"User-Agent": UA})
    for i in range(retry):
        try:
            return op.open(req, timeout=120).read().decode("utf-8", "replace")
        except Exception as e:
            if i == retry - 1:
                raise SystemExit(f"Gagal mengakses bi.go.id: {e}")
            time.sleep(3 * (i + 1))


def angka(s):  # "18.238,74" -> 18238.74
    return float(s.replace(".", "").replace(",", "."))


def form_fields(h):
    d = {}
    for m in re.finditer(r"<input[^>]*>", h):
        t = m.group(0)
        n = re.search(r'name="([^"]*)"', t)
        if not n:
            continue
        ty = (re.search(r'type="([^"]*)"', t) or [None, "text"])[1]
        if ty in ("submit", "image", "button", "checkbox"):
            continue
        v = re.search(r'value="([^"]*)"', t)
        d[html.unescape(n.group(1))] = html.unescape(v.group(1)) if v else ""
    for m in re.finditer(r'<select[^>]*name="([^"]*)"[^>]*>(.*?)</select>', h, re.S):
        o = re.search(r'<option[^>]*selected[^>]*value="([^"]*)"', m.group(2)) or \
            re.search(r'<option[^>]*value="([^"]*)"', m.group(2))
        d[html.unescape(m.group(1))] = html.unescape(o.group(1)) if o else ""
    return d


def baris(h):
    pola = (r"<td[^>]*>\s*([A-Z]{3})\s*</td>\s*<td[^>]*>\s*([\d.,]+)\s*</td>\s*"
            r"<td[^>]*>\s*([\d.,]+)\s*</td>\s*<td[^>]*>\s*([\d.,]+)\s*</td>")
    return [(k, angka(n), angka(j), angka(b)) for k, n, j, b in re.findall(pola, h)]


def nama_mata_uang(h):
    return {k: v.strip() for k, v in
            re.findall(r"<td[^>]*>\s*([A-Z]{3})\s*</td>\s*<td[^>]*>\s*([A-Z][A-Z .\-']+?)\s*</td>", h)}


def tanggal_terbaru(h):
    m = re.search(r"Update Terakhir\s*(?:&nbsp;|\s)*(\d+)\s+(\w+)\s+(\d{4})", h)
    if not m or m.group(2).lower() not in BULAN:
        raise SystemExit("Tidak bisa membaca tanggal 'Update Terakhir' dari halaman BI (struktur halaman berubah?).")
    return date(int(m.group(3)), BULAN[m.group(2).lower()], int(m.group(1)))


def kurs_tanggal(f, d):
    dmy = d.strftime("%d/%m/%Y")
    isian = dict(f)
    isian[P + "txtTanggal"] = dmy
    isian[P + "btnSearch2"] = "Cari"
    isian[P + "hidSourceID"] = P.replace("$", "_") + "btnSearch2"
    return baris(buka(urllib.parse.urlencode(isian).encode()))


def main():
    ap = argparse.ArgumentParser(description="Ambil Kurs Transaksi BI (semua mata uang) ke CSV.")
    ap.add_argument("--dari", help="tanggal awal YYYY-MM-DD (default: kurs terbaru saja)")
    ap.add_argument("--sampai", help="tanggal akhir YYYY-MM-DD (default: kurs terbaru)")
    ap.add_argument("--mata-uang", nargs="+", metavar="KODE", help="filter, mis. USD EUR JPY")
    ap.add_argument("--output", default="kurs_bi.csv", help="nama file CSV (default: kurs_bi.csv)")
    a = ap.parse_args()

    buka.jar = http.cookiejar.CookieJar()
    print("Mengambil halaman BI ...", flush=True)
    h = buka()
    terbaru = tanggal_terbaru(h)
    nama = nama_mata_uang(h)
    f = form_fields(h)
    filt = {k.upper() for k in a.mata_uang} if a.mata_uang else None

    awal = datetime.strptime(a.dari, "%Y-%m-%d").date() if a.dari else terbaru
    akhir = datetime.strptime(a.sampai, "%Y-%m-%d").date() if a.sampai else terbaru
    if awal > akhir:
        raise SystemExit("Tanggal awal harus sebelum tanggal akhir.")

    hasil = []  # (tanggal, kode, nama, nilai, jual, beli)
    d = awal
    while d <= akhir:
        if d.weekday() < 5 or d == terbaru:  # akhir pekan tidak ada kurs
            if d == terbaru:
                rows = baris(h)  # sudah ada di halaman awal
            else:
                rows = kurs_tanggal(f, d)
            rows = [r for r in rows if not filt or r[0] in filt]
            print(f"{d}  {len(rows):>2} mata uang" if rows else f"{d}  tidak ada data (libur)", flush=True)
            hasil += [(d.isoformat(), k, nama.get(k, ""), n, j, b) for k, n, j, b in rows]
        d += timedelta(days=1)

    if not hasil:
        raise SystemExit("Tidak ada data yang ditemukan.")
    with open(a.output, "w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig: langsung rapi di Excel
        w = csv.writer(fh)
        w.writerow(["tanggal", "kode", "nama", "nilai", "kurs_jual", "kurs_beli"])
        w.writerows(hasil)
    print(f"\nSelesai: {len(hasil)} baris disimpan ke {a.output}")

    # tampilkan ringkasan tanggal terakhir di layar
    tgl = hasil[-1][0]
    print(f"\nKurs {tgl}:")
    print(f"{'Kode':<5}{'Nilai':>8}{'Kurs Jual':>16}{'Kurs Beli':>16}")
    for t, k, n, v, j, b in hasil:
        if t == tgl:
            print(f"{k:<5}{v:>8,.0f}{j:>16,.2f}{b:>16,.2f}")


if __name__ == "__main__":
    main()
