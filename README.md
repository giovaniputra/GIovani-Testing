# GIovani-Testing
Coba coba aja

## Amazon Selling Partner API - top selling product

Reports the top selling product (by units ordered) for the previous day, using the Amazon Selling Partner Orders API.

### Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill in your SP-API app credentials (LWA client ID/secret, refresh token, IAM role ARN, AWS access keys, marketplace ID). Get these from Seller Central under *Apps & Services > Develop apps*.
3. `npm run top-seller`

The script queries orders created in the previous UTC day, fetches each order's line items, aggregates units ordered per ASIN, and prints the top seller plus the full ranking.

