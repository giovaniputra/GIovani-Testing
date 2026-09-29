require('dotenv').config();
const SellingPartnerAPI = require('amazon-sp-api');

function yesterdayRangeUTC() {
  const now = new Date();
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 1);
  return { createdAfter: start.toISOString(), createdBefore: end.toISOString() };
}

function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var: ${name}`);
  return value;
}

async function fetchYesterdaysOrders(sp, marketplaceId, createdAfter, createdBefore) {
  const orders = [];
  let nextToken;
  do {
    const response = await sp.callAPI({
      operation: 'getOrders',
      endpoint: 'orders',
      query: nextToken
        ? { NextToken: nextToken }
        : {
            MarketplaceIds: [marketplaceId],
            CreatedAfter: createdAfter,
            CreatedBefore: createdBefore,
          },
    });
    orders.push(...(response.Orders || []));
    nextToken = response.NextToken;
  } while (nextToken);
  return orders;
}

async function fetchOrderItems(sp, orderId) {
  const items = [];
  let nextToken;
  do {
    const response = await sp.callAPI({
      operation: 'getOrderItems',
      endpoint: 'orders',
      path: { orderId },
      query: nextToken ? { NextToken: nextToken } : undefined,
    });
    items.push(...(response.OrderItems || []));
    nextToken = response.NextToken;
  } while (nextToken);
  return items;
}

async function findTopSellingProduct() {
  const marketplaceId = requireEnv('SP_API_MARKETPLACE_ID');
  const { createdAfter, createdBefore } = yesterdayRangeUTC();

  const sp = new SellingPartnerAPI({
    region: process.env.SP_API_REGION || 'na',
    refresh_token: requireEnv('SP_API_REFRESH_TOKEN'),
    credentials: {
      SELLING_PARTNER_APP_CLIENT_ID: requireEnv('SP_API_CLIENT_ID'),
      SELLING_PARTNER_APP_CLIENT_SECRET: requireEnv('SP_API_CLIENT_SECRET'),
      AWS_ACCESS_KEY_ID: requireEnv('SP_API_ACCESS_KEY_ID'),
      AWS_SECRET_ACCESS_KEY: requireEnv('SP_API_SECRET_ACCESS_KEY'),
      AWS_SELLING_PARTNER_ROLE: requireEnv('SP_API_ROLE_ARN'),
    },
  });

  const orders = await fetchYesterdaysOrders(sp, marketplaceId, createdAfter, createdBefore);

  const unitsByAsin = new Map();
  for (const order of orders) {
    const items = await fetchOrderItems(sp, order.AmazonOrderId);
    for (const item of items) {
      const quantity = Number(item.QuantityOrdered) || 0;
      const entry = unitsByAsin.get(item.ASIN) || { title: item.Title, sku: item.SellerSKU, units: 0 };
      entry.units += quantity;
      unitsByAsin.set(item.ASIN, entry);
    }
  }

  const ranked = [...unitsByAsin.entries()]
    .map(([asin, data]) => ({ asin, ...data }))
    .sort((a, b) => b.units - a.units);

  return { range: { createdAfter, createdBefore }, orderCount: orders.length, ranked };
}

async function main() {
  const { range, orderCount, ranked } = await findTopSellingProduct();

  console.log(`Yesterday's window: ${range.createdAfter} -> ${range.createdBefore}`);
  console.log(`Orders found: ${orderCount}`);

  if (ranked.length === 0) {
    console.log('No units sold yesterday.');
    return;
  }

  const top = ranked[0];
  console.log('\nTop selling product yesterday:');
  console.log(`  Title: ${top.title}`);
  console.log(`  ASIN:  ${top.asin}`);
  console.log(`  SKU:   ${top.sku}`);
  console.log(`  Units: ${top.units}`);

  console.log('\nFull ranking:');
  ranked.forEach((p, i) => {
    console.log(`  ${i + 1}. ${p.title} (${p.asin}) - ${p.units} units`);
  });
}

if (require.main === module) {
  main().catch((err) => {
    console.error('Failed to fetch top selling product:', err.message);
    process.exit(1);
  });
}

module.exports = { findTopSellingProduct, yesterdayRangeUTC };
