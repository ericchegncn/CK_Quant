import { normalizeAdminConfigSource } from '@/utils/adminConfig';
import { describe, expect, it } from 'vitest';

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
