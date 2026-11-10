const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const { DatabaseSync } = require('node:sqlite');
const src = require('./source');
const db = new DatabaseSync(process.env.SKP_DB || path.join(__dirname, 'skp.db'));
db.exec(`CREATE TABLE IF NOT EXISTS skp_source(PlanID INTEGER PRIMARY KEY,NIK,Nama,Departemen,Periode,Sasaran,Target REAL,Satuan,Bobot REAL);
CREATE TABLE IF NOT EXISTS skp_collection(PlanID INTEGER PRIMARY KEY,Realisasi REAL,Catatan TEXT,Status TEXT NOT NULL DEFAULT 'Belum',UpdatedAt TEXT);`);
// Format SKP ID: SKPMMYYNNNNNNN (MMYY = bulan/tahun saat baris pertama masuk, N = nomor urut 7 digit, reset tiap bulan).
if (!db.prepare("SELECT 1 FROM pragma_table_info('skp_source') WHERE name='SkpID'").get()) db.exec('ALTER TABLE skp_source ADD COLUMN SkpID TEXT');
db.exec("UPDATE skp_source SET SkpID='SKP'||SUBSTR(SkpID,5,4)||printf('%07d',CAST(SUBSTR(SkpID,10) AS INTEGER)) WHERE SkpID LIKE 'SKP-%'"); // migrasi format lama
db.exec('CREATE UNIQUE INDEX IF NOT EXISTS ux_skpid ON skp_source(SkpID)');
function nextSkpId(prefix) {
  const r = db.prepare('SELECT MAX(CAST(SUBSTR(SkpID, ?) AS INTEGER)) m FROM skp_source WHERE SkpID LIKE ?').get(prefix.length + 1, prefix + '%');
  return prefix + String((r.m || 0) + 1).padStart(7, '0');
}
function newPrefix(d = new Date()) { return 'SKP' + String(d.getMonth() + 1).padStart(2, '0') + String(d.getFullYear()).slice(-2); }
async function sync() {
  const rows = await src.fetchSourceRows(); let n = 0, added = 0;
  const upd = db.prepare('UPDATE skp_source SET NIK=?,Nama=?,Departemen=?,Periode=?,Sasaran=?,Target=?,Satuan=?,Bobot=? WHERE PlanID=?');
  const ins = db.prepare('INSERT INTO skp_source(PlanID,NIK,Nama,Departemen,Periode,Sasaran,Target,Satuan,Bobot,SkpID) VALUES(?,?,?,?,?,?,?,?,?,?)');
  const has = db.prepare('SELECT 1 FROM skp_source WHERE PlanID=?');
  db.exec('BEGIN');
  try {
    for (const r of rows) {
      n++;
      if (has.get(r.PlanID)) upd.run(r.NIK,r.Nama,r.Departemen,r.Periode,r.Sasaran,r.Target,r.Satuan,r.Bobot,r.PlanID);
      else { ins.run(r.PlanID,r.NIK,r.Nama,r.Departemen,r.Periode,r.Sasaran,r.Target,r.Satuan,r.Bobot,nextSkpId(newPrefix())); added++; }
    }
    // baris lama tanpa SkpID (dari versi sebelumnya) diberi ID
    for (const r of db.prepare('SELECT PlanID FROM skp_source WHERE SkpID IS NULL ORDER BY PlanID').all())
      db.prepare('UPDATE skp_source SET SkpID=? WHERE PlanID=?').run(nextSkpId(newPrefix()), r.PlanID);
    db.exec('COMMIT');
  } catch (e) { db.exec('ROLLBACK'); throw e; }
  return { synced: n, baru: added };
}
const SELECT = `SELECT s.*,COALESCE(c.Status,'Belum') Status,c.Realisasi,c.Catatan,c.UpdatedAt,
 CASE WHEN c.Realisasi IS NOT NULL AND s.Target>0 THEN ROUND(c.Realisasi*100.0/s.Target,1) END Capaian
 FROM skp_source s LEFT JOIN skp_collection c USING(PlanID)`;
function list(q) {
  const w = [], p = [];
  if (q.periode) { w.push('s.Periode=?'); p.push(q.periode); }
  if (q.dept) { w.push('s.Departemen=?'); p.push(q.dept); }
  if (q.status) { w.push("COALESCE(c.Status,'Belum')=?"); p.push(q.status); }
  if (q.q) { w.push('(s.Nama LIKE ? OR s.NIK LIKE ? OR s.Sasaran LIKE ? OR s.SkpID LIKE ?)'); p.push(...Array(4).fill('%' + q.q + '%')); }
  return db.prepare(SELECT + (w.length ? ' WHERE ' + w.join(' AND ') : '') + ' ORDER BY s.SkpID').all(...p);
}
const send = (res, code, body, type = 'application/json') => { res.writeHead(code, { 'Content-Type': type }); res.end(type === 'application/json' ? JSON.stringify(body) : body); };
const body = req => new Promise(r => { let d = ''; req.on('data', c => d += c); req.on('end', () => { try { r(JSON.parse(d || '{}')); } catch { r(null); } }); });
const csvCell = v => { v = v == null ? '' : String(v); if (/^[=+\-@]/.test(v)) v = "'" + v; return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
async function main() {
if (!db.prepare('SELECT 1 FROM skp_source LIMIT 1').get()) await sync();
http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x'), q = Object.fromEntries(u.searchParams);
  try {
    if (u.pathname === '/api/meta') return send(res, 200, { mode: src.mode,
      periode: db.prepare('SELECT DISTINCT Periode v FROM skp_source ORDER BY 1').all().map(x => x.v),
      dept: db.prepare('SELECT DISTINCT Departemen v FROM skp_source ORDER BY 1').all().map(x => x.v) });
    if (u.pathname === '/api/rows' && req.method === 'GET') return send(res, 200, list(q));
    if (u.pathname === '/api/summary') {
      const rows = list(q), by = s => rows.filter(r => r.Status === s).length;
      return send(res, 200, { total: rows.length, belum: by('Belum'), draft: by('Draft'), submitted: by('Submitted') });
    }
    if (u.pathname === '/api/sync' && req.method === 'POST') return send(res, 200, await sync());
    if (u.pathname === '/api/export.csv') {
      const cols = ['SkpID','PlanID','NIK','Nama','Departemen','Periode','Sasaran','Target','Satuan','Bobot','Realisasi','Capaian','Status','Catatan','UpdatedAt'];
      const out = [cols.join(',')].concat(list(q).map(r => cols.map(c => csvCell(r[c])).join(',')));
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="skp-collection.csv"' });
      return res.end('﻿' + out.join('\n'));
    }
    const m = u.pathname.match(/^\/api\/rows\/(\d+)\/collect$/);
    if (m && req.method === 'POST') {
      const b = await body(req); if (!b) return send(res, 400, { error: 'JSON tidak valid' });
      const id = +m[1];
      if (!db.prepare('SELECT 1 FROM skp_source WHERE PlanID=?').get(id)) return send(res, 404, { error: 'PlanID tidak ada' });
      if (!['Draft', 'Submitted'].includes(b.status)) return send(res, 400, { error: 'status harus Draft/Submitted' });
      const real = b.realisasi === '' || b.realisasi == null ? null : Number(b.realisasi);
      if (real !== null && !Number.isFinite(real)) return send(res, 400, { error: 'realisasi harus angka' });
      if (b.status === 'Submitted' && real === null) return send(res, 400, { error: 'realisasi wajib diisi untuk Submit' });
      const cur = db.prepare('SELECT Status FROM skp_collection WHERE PlanID=?').get(id);
      if (cur && cur.Status === 'Submitted') return send(res, 409, { error: 'Sudah Submitted, tidak bisa diubah' });
      db.prepare(`INSERT INTO skp_collection(PlanID,Realisasi,Catatan,Status,UpdatedAt) VALUES(?,?,?,?,datetime('now'))
        ON CONFLICT(PlanID) DO UPDATE SET Realisasi=excluded.Realisasi,Catatan=excluded.Catatan,Status=excluded.Status,UpdatedAt=excluded.UpdatedAt`)
        .run(id, real, String(b.catatan || '').slice(0, 500), b.status);
      return send(res, 200, db.prepare(SELECT + ' WHERE s.PlanID=?').get(id));
    }
    if (u.pathname === '/' || u.pathname === '/index.html') return send(res, 200, fs.readFileSync(path.join(__dirname, 'public/index.html')), 'text/html; charset=utf-8');
    send(res, 404, { error: 'not found' });
  } catch (e) { console.error(e); send(res, 500, { error: 'server error' }); }
}).listen(process.env.PORT || 3000, () => console.log('SKP Collection (' + src.mode + ') http://localhost:' + (process.env.PORT || 3000)));
}
main().catch(e => { console.error('Gagal start:', e.message); process.exit(1); });
