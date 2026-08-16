import { applyManualPairWhitelist, normalizeAdminConfigSource } from '@/utils/adminConfig';
import { describe, expect, it } from 'vitest';

describe('applyManualPairWhitelist', () => {
  it('switches VolumePairList to StaticPairList when a manual whitelist is selected', () => {
    const config = {
      exchange: { name: 'binance', pair_whitelist: ['BTC/USDT:USDT'] },
      pairlists: [
        {
          method: 'VolumePairList',
          number_assets: 30,
          sort_key: 'quoteVolume',
          refresh_period: 300,
        },
      ],
    };

    expect(applyManualPairWhitelist(config, ['ETH/USDT:USDT', 'SOL/USDT:USDT'])).toEqual({
      exchange: {
        name: 'binance',
        pair_whitelist: ['ETH/USDT:USDT', 'SOL/USDT:USDT'],
      },
      pairlists: [{ method: 'StaticPairList' }],
    });
  });

  it('preserves filters after replacing the dynamic pairlist generator', () => {
    const ageFilter = { method: 'AgeFilter', min_days_listed: 7 };
    const result = applyManualPairWhitelist(
      {
        exchange: { pair_whitelist: [] },
        pairlists: [{ method: 'VolumePairList', number_assets: 20 }, ageFilter],
      },
      ['BTC/USDT:USDT'],
    );

    expect(result.pairlists).toEqual([{ method: 'StaticPairList' }, ageFilter]);
  });

  it('adds StaticPairList when pairlists is missing', () => {
    const result = applyManualPairWhitelist({ exchange: { name: 'binance' } }, ['BTC/USDT:USDT']);

    expect(result).toEqual({
      exchange: { name: 'binance', pair_whitelist: ['BTC/USDT:USDT'] },
      pairlists: [{ method: 'StaticPairList' }],
    });
  });

  it('keeps an existing StaticPairList configuration unchanged', () => {
    const pairlists = [{ method: 'StaticPairList', allow_inactive: true }];
    const result = applyManualPairWhitelist({ exchange: { pair_whitelist: [] }, pairlists }, [
      'BTC/USDT:USDT',
    ]);

    expect(result.pairlists).toEqual(pairlists);
  });
});

describe('normalizeAdminConfigSource', () => {
  it('converts a numeric stake amount string to a JSON number', () => {
    const normalized = normalizeAdminConfigSource(
      JSON.stringify({ stake_amount: '3', max_open_trades: 100 }),
    );

    expect(JSON.parse(normalized)).toEqual({ stake_amount: 3, max_open_trades: 100 });
  });

  it('supports decimal and padded numeric values', () => {
    const normalized = normalizeAdminConfigSource(JSON.stringify({ stake_amount: ' 2.5 ' }));

    expect(JSON.parse(normalized).stake_amount).toBe(2.5);
  });

  it('preserves unlimited and invalid values for server validation', () => {
    const unlimited = JSON.stringify({ stake_amount: 'unlimited' });
    const invalid = JSON.stringify({ stake_amount: 'not-a-number' });

    expect(normalizeAdminConfigSource(unlimited)).toBe(unlimited);
    expect(normalizeAdminConfigSource(invalid)).toBe(invalid);
  });

  it('does not rewrite invalid JSON', () => {
    const invalidJson = '{"stake_amount": 3';

    expect(normalizeAdminConfigSource(invalidJson)).toBe(invalidJson);
  });
});
