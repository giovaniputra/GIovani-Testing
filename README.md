# GIovani-Testing
Coba coba aja

## Amazon Selling Partner API - top selling product

Reports the top selling product (by units ordered) for the previous day, using the Amazon Selling Partner Orders API.

### Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill in your SP-API app credentials (LWA client ID/secret, refresh token, IAM role ARN, AWS access keys, marketplace ID). Get these from Seller Central under *Apps & Services > Develop apps*.
3. `npm run top-seller`

The script queries orders created in the previous UTC day, fetches each order's line items, aggregates units ordered per ASIN, and prints the top seller plus the full ranking.

## SQL Server connection

A reusable connection module (`src/db/connection.js`) for reading and writing app data in SQL Server via SQL login authentication.

### Setup

1. `npm install`
2. In `.env`, fill in `SQL_SERVER_HOST`, `SQL_SERVER_PORT`, `SQL_SERVER_DATABASE`, `SQL_SERVER_USER`, `SQL_SERVER_PASSWORD`. Set `SQL_SERVER_TRUST_SERVER_CERT=true` only for local/dev servers with a self-signed cert.
3. `npm run db:test` to verify connectivity.

### Usage

```js
const { query, closePool } = require('./src/db/connection');

const result = await query('SELECT * FROM Orders WHERE Status = @status', { status: 'Pending' });
console.log(result.recordset);

await closePool();
```

See `src/db/example.js` for parameterized read/write helpers. Table and column names in that file are meant to be hardcoded by the developer, not built from user input — only values should ever come from `params`/`columns` to avoid SQL injection.

