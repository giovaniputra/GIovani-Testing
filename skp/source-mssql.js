// Sumber data asli: [DB_TRANS].[dbo].[TBAnaplansys20]. Koneksi dari .env (lihat .env.example).
// EDIT MAP di bawah sesuai nama kolom asli tabel (jalankan `npm run inspect` untuk melihatnya).
const sql = require('mssql');
const MAP = { PlanID: 'PlanID', NIK: 'NIK', Nama: 'Nama', Departemen: 'Departemen', Periode: 'Periode', Sasaran: 'Sasaran', Target: 'Target', Satuan: 'Satuan', Bobot: 'Bobot' };
const cfg = () => ({ server: process.env.DB_SERVER, port: +(process.env.DB_PORT || 1433), user: process.env.DB_USER, password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'DB_TRANS', options: { encrypt: process.env.DB_ENCRYPT === 'true', trustServerCertificate: true }, requestTimeout: 30000 });
async function query(text) { const pool = await new sql.ConnectionPool(cfg()).connect(); try { return (await pool.request().query(text)).recordset; } finally { await pool.close(); } }
async function fetchSourceRows() {
  const rows = await query('SELECT * FROM [DB_TRANS].[dbo].[TBAnaplansys20]');
  return rows.map((r, i) => Object.fromEntries(Object.entries(MAP).map(([k, col]) => [k, k === 'PlanID' && r[col] == null ? i + 1 : r[col]])));
}
module.exports = { fetchSourceRows, query, mode: 'SQL SERVER' };
