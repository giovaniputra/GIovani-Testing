const { query, closePool } = require('./connection');

async function main() {
  const result = await query('SELECT @@VERSION AS version, DB_NAME() AS db, SYSUTCDATETIME() AS now');
  console.log('Connected successfully.');
  console.table(result.recordset);
}

main()
  .catch((err) => {
    console.error('SQL Server connection failed:', err.message);
    process.exitCode = 1;
  })
  .finally(() => closePool());
