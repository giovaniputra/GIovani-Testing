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
- Filter mata uang, dan Δ Jual terhadap tanggal sebelumnya yang pernah diambil.
- Data disimpan di `cache.json` (tidak masuk git).

Halaman harus dibuka lewat `server.js` (bukan klik dua kali file HTML), karena browser tidak boleh
mengambil data bi.go.id langsung (CORS).
