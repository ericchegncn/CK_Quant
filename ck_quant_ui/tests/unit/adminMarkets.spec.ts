import type { AdminMarketSummary } from '@/types';
import { filterAdminMarkets, setPairWhitelisted, sortAdminMarkets } from '@/utils/adminMarkets';
import { describe, expect, it } from 'vitest';

const markets: AdminMarketSummary[] = [
  {
    pair: 'ETH/USDT:USDT',
    base: 'ETH',
    quote: 'USDT',
    last: 3000,
    quote_volume: 500,
    percentage: -3,
  },
  {
    pair: 'BTC/USDT:USDT',
    base: 'BTC',
    quote: 'USDT',
    last: 60000,
    quote_volume: 1000,
    percentage: 2,
  },
  {
    pair: 'NEW/USDT:USDT',
    base: 'NEW',
    quote: 'USDT',
    last: null,
    quote_volume: null,
    percentage: null,
  },
];

describe('admin market helpers', () => {
  it('sorts volume and percentage with missing values last', () => {
    expect(sortAdminMarkets(markets, 'volume').map((market) => market.base)).toEqual([
      'BTC',
      'ETH',
      'NEW',
    ]);
    expect(sortAdminMarkets(markets, 'gainers').map((market) => market.base)).toEqual([
      'BTC',
      'ETH',
      'NEW',
    ]);
    expect(sortAdminMarkets(markets, 'losers').map((market) => market.base)).toEqual([
      'ETH',
      'BTC',
      'NEW',
    ]);
  });

  it('filters by pair components case-insensitively', () => {
    expect(filterAdminMarkets(markets, 'eth').map((market) => market.pair)).toEqual([
      'ETH/USDT:USDT',
    ]);
  });

  it('adds pairs once and removes exact pairs without changing other entries', () => {
    expect(setPairWhitelisted(['BTC/USDT:USDT'], 'ETH/USDT:USDT', true)).toEqual([
      'BTC/USDT:USDT',
      'ETH/USDT:USDT',
    ]);
    expect(setPairWhitelisted(['BTC/USDT:USDT', 'ETH/USDT:USDT'], 'BTC/USDT:USDT', false)).toEqual([
      'ETH/USDT:USDT',
    ]);
  });
});
