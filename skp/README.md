# SKP Collection (simulasi)

Aplikasi pengumpulan realisasi SKP berdasarkan baris data sumber. Backend Node 22 + SQLite bawaan, tanpa `npm install`.

## Jalankan
    npm start        # http://localhost:3000  (PORT=... untuk ganti port)

## Fitur
Filter periode/departemen/status/pencarian, isi realisasi (Draft atau Submit), capaian %, ekspor CSV. Setelah Submitted, baris terkunci.

## Status: SIMULASI
`source.js` membangkitkan baris palsu yang meniru `[DB_TRANS].[dbo].[TBAnaplansys20]`.
Kolom yang dipakai (PlanID, NIK, Nama, Departemen, Periode, Sasaran, Target, Satuan, Bobot) adalah ASUMSI.
Untuk data asli: ganti `fetchSourceRows()` dengan query `mssql` dari jaringan yang bisa menjangkau server,
petakan kolom asli ke bentuk yang sama. Kredensial lewat environment/.env, jangan di-commit.
