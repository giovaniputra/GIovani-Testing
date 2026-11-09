// Tampilkan 5 baris + daftar kolom tabel asli. Kirim hasilnya ke Claude untuk mencocokkan MAP.
require('node:fs').existsSync('.env') && process.loadEnvFile('.env');
const { query } = require('./source-mssql');
query('SELECT TOP 5 * FROM [DB_TRANS].[dbo].[TBAnaplansys20]').then(r => { console.log('Kolom:', Object.keys(r[0] || {}).join(', ')); console.table(r); }).catch(e => { console.error('Gagal:', e.message); process.exit(1); });
