const { sql, getPool, query, closePool } = require('./connection');

// Example: parameterized read
async function findById(table, id) {
  const result = await query(`SELECT * FROM ${table} WHERE Id = @id`, { id });
  return result.recordset[0];
}

// Example: parameterized write using an explicit request (typed params)
async function insertRow(table, columns) {
  const pool = await getPool();
  const request = pool.request();
  for (const [name, value] of Object.entries(columns)) {
    request.input(name, value);
  }
  const columnNames = Object.keys(columns).join(', ');
  const paramNames = Object.keys(columns).map((c) => `@${c}`).join(', ');
  const result = await request.query(
    `INSERT INTO ${table} (${columnNames}) OUTPUT INSERTED.* VALUES (${paramNames})`
  );
  return result.recordset[0];
}

module.exports = { sql, findById, insertRow, closePool };
