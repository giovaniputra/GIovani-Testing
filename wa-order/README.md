# WA Order Intake

Toko tetap memesan lewat WhatsApp seperti biasa. Sistem membaca chat, menyusunnya menjadi order terstruktur, memvalidasi, lalu membalas konfirmasi singkat di chat yang sama.

Cakupan versi ini adalah empat langkah pertama dari alur target:

| # | Langkah | File |
|---|---|---|
| 1 | Gerbang WhatsApp (webhook Cloud API, verifikasi token dan tanda tangan, anti-duplikat) | `app/main.py` |
| 2 | Order parser (teks bebas Bahasa Indonesia, angka kata, "seperti biasa"). LLM opsional | `app/parser.py` |
| 3 | Matching dan validasi (toko dari nomor WA, alias SKU, fuzzy match, stok, limit kredit, overdue, anomali qty) | `app/engine.py` |
| 4 | Konfirmasi balik ke toko (ringkasan, pilih nomor bila ambigu, OK / ubah / batal) | `app/replier.py`, `app/service.py` |

Belum ada: push ke ERP/DMS dan picking list gudang (langkah 5-7), voice note dan foto (ditandai `needs_review`), UI koreksi admin.

## Jalankan

```bash
cd wa-order
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Buka http://localhost:8000 untuk simulator chat. Tidak butuh akun WhatsApp.

```bash
python -m pytest -q
```

## Hubungkan ke WhatsApp Cloud API

Atur environment variable berikut, lalu arahkan webhook Meta ke `https://<domain>/webhook`.

| Variabel | Fungsi |
|---|---|
| `WHATSAPP_VERIFY_TOKEN` | Token verifikasi webhook (default dev: `dev-verify-token`) |
| `WHATSAPP_APP_SECRET` | Memvalidasi `X-Hub-Signature-256`. Wajib di produksi |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | Mengirim balasan. Jika kosong, balasan hanya masuk tabel `outbox` |
| `ANTHROPIC_API_KEY` (opsional) | Ekstraksi order oleh LLM. Jika kosong atau gagal, memakai parser aturan |
| `WA_MASTER`, `WA_ORDER_DB` | Lokasi master data JSON dan database SQLite |

Catatan:
- Jalur LLM dan pengiriman ke Cloud API ditulis sesuai dokumentasi tetapi belum diuji terhadap layanan asli. Jalur aturan dan simulasi sudah diuji.
- Pesan balasan di luar jendela 24 jam sejak pesan terakhir toko memerlukan template WhatsApp yang disetujui Meta.

## Perilaku penting

- Hanya hal yang perlu dijawab toko yang ditanyakan (misalnya produk ambigu). Isu kredit, overdue, stok dan anomali tidak pernah dibuka ke toko. Toko hanya menerima "pesanan sudah kami terima".
- Obrolan biasa ("kapan barang sampai?") diabaikan bot supaya salesman yang membalas.
- Webhook idempoten (dedupe berdasarkan id pesan WhatsApp).

## Master data

`data/master.json` berisi **data dummy**. Ganti dengan export customer dan SKU asli. Kualitas alias SKU per toko sangat menentukan akurasi.
