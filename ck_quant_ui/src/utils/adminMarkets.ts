import type { AdminMarketSummary } from '@/types';

export type AdminMarketSort = 'volume' | 'gainers' | 'losers';

function metric(market: AdminMarketSummary, sort: AdminMarketSort) {
  return sort === 'volume' ? market.quote_volume : market.percentage;
}

export function sortAdminMarkets(markets: AdminMarketSummary[], sort: AdminMarketSort) {
  return [...markets].sort((left, right) => {
    const leftValue = metric(left, sort);
    const rightValue = metric(right, sort);
    if (leftValue == null && rightValue == null) return left.pair.localeCompare(right.pair);
    if (leftValue == null) return 1;
    if (rightValue == null) return -1;
    const difference = sort === 'losers' ? leftValue - rightValue : rightValue - leftValue;
    return difference || left.pair.localeCompare(right.pair);
  });
}

export function filterAdminMarkets(markets: AdminMarketSummary[], search: string) {
  const needle = search.trim().toLocaleUpperCase();
  if (!needle) return markets;
  return markets.filter((market) =>
    `${market.pair} ${market.base} ${market.quote}`.toLocaleUpperCase().includes(needle),
  );
}

export function setPairWhitelisted(whitelist: string[], pair: string, selected: boolean) {
  const normalized = whitelist.map((item) => item.trim()).filter(Boolean);
  if (selected) return normalized.includes(pair) ? normalized : [...normalized, pair];
  return normalized.filter((item) => item !== pair);
}
