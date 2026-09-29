require('dotenv').config();
const sql = require('mssql');

function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var: ${name}`);
  return value;
}

const config = {
  server: () => requireEnv('SQL_SERVER_HOST'),
  port: Number(process.env.SQL_SERVER_PORT) || 1433,
  database: () => requireEnv('SQL_SERVER_DATABASE'),
  user: () => requireEnv('SQL_SERVER_USER'),
  password: () => requireEnv('SQL_SERVER_PASSWORD'),
  options: {
    encrypt: (process.env.SQL_SERVER_ENCRYPT || 'true').toLowerCase() === 'true',
    trustServerCertificate: (process.env.SQL_SERVER_TRUST_SERVER_CERT || 'false').toLowerCase() === 'true',
  },
};

let pool;

function getPool() {
  if (!pool) {
    pool = new sql.ConnectionPool({
      server: config.server(),
      port: config.port,
      database: config.database(),
      user: config.user(),
      password: config.password(),
      options: config.options,
    }).connect();
  }
  return pool;
}

async function query(text, params = {}) {
  const connectedPool = await getPool();
  const request = connectedPool.request();
  for (const [name, value] of Object.entries(params)) {
    request.input(name, value);
  }
  return request.query(text);
}

async function closePool() {
  if (pool) {
    const connectedPool = await pool;
    await connectedPool.close();
    pool = undefined;
  }
}

module.exports = { sql, getPool, query, closePool };
