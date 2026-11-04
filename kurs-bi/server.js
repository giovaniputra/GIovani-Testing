// Kurs Transaksi BI viewer — zero dependencies. Run: node server.js → http://localhost:3000
// Source: https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx
const http = require("http"), fs = require("fs"), path = require("path");
const BI = "https://www.bi.go.id/id/statistik/informasi-kurs/transaksi-bi/Default.aspx";
const CACHE = path.join(__dirname, "cache.json");
const UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36";
const MON = { januari:1, februari:2, maret:3, april:4, mei:5, juni:6, juli:7, agustus:8, september:9, oktober:10, november:11, desember:12 };
const P = "ctl00$ctl51$g_6c89d4ad_107f_437d_bd54_8fda17b556bf$ctl00$";
const pad = n => String(n).padStart(2, "0");
const unesc = s => s.replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
const num = s => parseFloat(s.replace(/\./g, "").replace(",", "."));

// cache = { updated: "YYYY-MM-DD" (latest date BI reports), names: {USD:"US DOLLAR"}, days: { "YYYY-MM-DD": [[code,nilai,jual,beli],...] } }
const load = () => { try { return JSON.parse(fs.readFileSync(CACHE, "utf8")); } catch { return { updated: null, names: {}, days: {} }; } };
const save = c => fs.writeFileSync(CACHE, JSON.stringify(c));

let cookies = {};
async function req(body) {
  const headers = { "User-Agent": UA, Cookie: Object.entries(cookies).map(([k, v]) => k + "=" + v).join("; ") };
  if (body) headers["Content-Type"] = "application/x-www-form-urlencoded";
  const r = await fetch(BI, { method: body ? "POST" : "GET", headers, body, signal: AbortSignal.timeout(120000) });
  for (const c of r.headers.getSetCookie?.() || []) { const [kv] = c.split(";"); const i = kv.indexOf("="); cookies[kv.slice(0, i)] = kv.slice(i + 1); }
  if (!r.ok) throw new Error("bi.go.id responded " + r.status);
  return r.text();
}
function fields(h) {
  const d = {};
  for (const m of h.matchAll(/<input[^>]*>/g)) {
    const t = m[0], n = /name="([^"]*)"/.exec(t); if (!n) continue;
    const ty = (/type="([^"]*)"/.exec(t) || [, "text"])[1];
    if (["submit", "image", "button", "checkbox"].includes(ty)) continue;
    d[unesc(n[1])] = unesc((/value="([^"]*)"/.exec(t) || [, ""])[1]);
  }
  for (const m of h.matchAll(/<select[^>]*name="([^"]*)"[^>]*>([\s\S]*?)<\/select>/g)) {
    const o = /<option[^>]*selected[^>]*value="([^"]*)"/.exec(m[2]) || /<option[^>]*value="([^"]*)"/.exec(m[2]);
    d[unesc(m[1])] = o ? unesc(o[1]) : "";
  }
  return d;
}
const parseRows = h => [...h.matchAll(/<td[^>]*>\s*([A-Z]{3})\s*<\/td>\s*<td[^>]*>\s*([\d.,]+)\s*<\/td>\s*<td[^>]*>\s*([\d.,]+)\s*<\/td>\s*<td[^>]*>\s*([\d.,]+)\s*<\/td>/g)]
  .map(m => [m[1], num(m[2]), num(m[3]), num(m[4])]);
const parseNames = h => Object.fromEntries([...h.matchAll(/<td[^>]*>\s*([A-Z]{3})\s*<\/td>\s*<td[^>]*>\s*([A-Z][A-Z .\-']+?)\s*<\/td>/g)].map(m => [m[1], m[2]]));
function parseUpdated(h) {
  const m = /Update Terakhir\s*(?:&nbsp;|\s)*(\d+)\s+(\w+)\s+(\d{4})/.exec(h);
  const mo = m && MON[m[2].toLowerCase()];
  return mo ? `${m[3]}-${pad(mo)}-${pad(+m[1])}` : null;
}

async function fetchLatest() {
  cookies = {};
  const h = await req(), rows = parseRows(h), date = parseUpdated(h);
  if (!rows.length || !date) throw new Error("Tabel kurs tidak ditemukan di halaman BI (struktur halaman mungkin berubah).");
  const c = load(); c.updated = date; c.days[date] = rows; Object.assign(c.names, parseNames(h)); save(c);
  return c;
}
async function fetchDate(iso) {
  const c0 = load(); if (c0.days[iso]) return { c: c0, found: true };
  cookies = {};
  const h0 = await req(), f = fields(h0), dmy = `${iso.slice(8)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
  const h = await req(new URLSearchParams({ ...f, [P + "txtTanggal"]: dmy, [P + "btnSearch2"]: "Cari", [P + "hidSourceID"]: P.replace(/\$/g, "_") + "btnSearch2" }).toString());
  const rows = parseRows(h), c = load();
  if (rows.length) { c.days[iso] = rows; save(c); }
  return { c, found: rows.length > 0 };
}
const view = (c, date) => {
  const dates = Object.keys(c.days).sort(), d = date && c.days[date] ? date : c.updated;
  const prevD = dates.filter(x => x < d).pop(), prev = prevD ? Object.fromEntries(c.days[prevD].map(r => [r[0], r])) : {};
  return { date: d, updated: c.updated, prevDate: prevD || null, names: c.names, dates,
    rows: (c.days[d] || []).map(([k, n, j, b]) => ({ code: k, nilai: n, jual: j, beli: b, dJual: prev[k] ? j - prev[k][2] : null })) };
};

let busy = null;
const send = (res, code, obj) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); };
http.createServer(async (rq, res) => {
  try {
    const u = new URL(rq.url, "http://x");
    if (u.pathname === "/api/state") { let c = load(); if (!c.updated) { busy = busy || fetchLatest().finally(() => busy = null); c = await busy; } return send(res, 200, view(c, u.searchParams.get("date"))); }
    if (u.pathname === "/api/refresh" && rq.method === "POST") { busy = busy || fetchLatest().finally(() => busy = null); const c = await busy; return send(res, 200, { ...view(c), fetchedAt: new Date().toISOString() }); }
    if (u.pathname === "/api/date" && rq.method === "POST") {
      const d = u.searchParams.get("d"); if (!/^\d{4}-\d{2}-\d{2}$/.test(d || "")) return send(res, 400, { error: "Format tanggal tidak valid" });
      const { c, found } = await fetchDate(d); return send(res, 200, found ? view(c, d) : { error: "Tidak ada data kurs untuk tanggal " + d + " (akhir pekan/libur?)" });
    }
    if (u.pathname === "/") { res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }); return res.end(fs.readFileSync(path.join(__dirname, "index.html"))); }
    res.writeHead(404); res.end();
  } catch (e) { send(res, 502, { error: e.message }); }
}).listen(process.env.PORT || 3000, () => console.log("Kurs BI app: http://localhost:" + (process.env.PORT || 3000)));
