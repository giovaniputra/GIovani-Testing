// Sumber data. MODE SIMULASI: membangkitkan baris palsu yang meniru [DB_TRANS].[dbo].[TBAnaplansys20].
// Kolom di bawah ADALAH ASUMSI (struktur asli belum diketahui). Untuk data asli, ganti fetchSourceRows()
// dengan query mssql dan petakan kolom aslinya ke bentuk yang sama.
const names = ['Andi Pratama','Siti Rahma','Budi Santoso','Dewi Lestari','Rizky Maulana','Putri Ayu','Fajar Nugroho','Intan Permata','Agus Wijaya','Maya Sari'];
const depts = ['Produksi','QC','Supply Chain','HR','Finance'];
const goals = [['Output produksi',1000,'unit'],['Efisiensi OEE',85,'%'],['Reject rate maks',2,'%'],['Pelatihan selesai',4,'sesi'],['Penghematan biaya',50,'juta'],['On-time delivery',95,'%']];
function fetchSourceRows() {
  const rows = []; let id = 1;
  names.forEach((n, i) => {
    for (const p of ['2026-S1', '2026-S2']) for (let g = 0; g < 3; g++) {
      const [sasaran, target, satuan] = goals[(i + g) % goals.length];
      rows.push({ PlanID: id++, NIK: 'G' + String(1000 + i), Nama: n, Departemen: depts[i % depts.length],
        Periode: p, Sasaran: sasaran, Target: target, Satuan: satuan, Bobot: [40, 35, 25][g] });
    }
  });
  return rows;
}
module.exports = { fetchSourceRows, mode: 'SIMULASI' };
