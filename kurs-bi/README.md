# Kurs Transaksi BI

Menampilkan Kurs Transaksi Bank Indonesia dari
https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx

## Jalankan
Butuh Node.js 18+ (tanpa dependensi lain):

    node server.js

Buka http://localhost:3000

## Fitur
- Tombol **Refresh dari bi.go.id**: mengambil kurs terbaru langsung dari situs BI (10–60 detik).
- **Cari tanggal**: kurs harian untuk tanggal tertentu (akhir pekan/libur: tidak ada data).
- Kurs Tengah = (Kurs Jual + Kurs Beli) / 2 / Nilai (di tabel web dan kolom `kurs_tengah` di CSV).
- Filter mata uang, dan Δ Jual terhadap tanggal sebelumnya yang pernah diambil.
- Data disimpan di `cache.json` (tidak masuk git).

Halaman harus dibuka lewat `server.js` (bukan klik dua kali file HTML), karena browser tidak boleh
mengambil data bi.go.id langsung (CORS).

## Otomasi di Windows (cukup klik dua kali)
| File | Fungsi |
|---|---|
| `jalankan_app.bat` | Menjalankan aplikasi web dan membuka browser |
| `ambil_kurs.bat` | Mengunduh kurs terbaru ke `hasil\kurs_TANGGAL.csv` (log: `hasil\log.txt`) |
| `pasang_jadwal.bat` | Memasang jadwal otomatis: Senin-Jumat jam 17:00 menjalankan `ambil_kurs.bat` |
| `hapus_jadwal.bat` | Menghapus jadwal otomatis |

Komputer harus menyala pada jam jadwal. Ganti jam dengan mengubah `17:00` di `pasang_jadwal.bat`, lalu klik dua kali lagi.
Untuk rentang tanggal, jalankan lewat Command Prompt: `ambil_kurs.bat --dari 2026-10-01 --sampai 2026-10-31`.
