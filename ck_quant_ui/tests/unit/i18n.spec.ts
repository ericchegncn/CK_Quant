import { describe, expect, it } from 'vitest';

import { normalizeLocale, supportedLocales } from '@/i18n';
import de from '@/i18n/locales/de';
import en from '@/i18n/locales/en';
import fr from '@/i18n/locales/fr';
import ja from '@/i18n/locales/ja';
import ko from '@/i18n/locales/ko';
import zhCN from '@/i18n/locales/zh-CN';
import zhTW from '@/i18n/locales/zh-TW';

function flattenKeys(value: unknown, prefix = ''): string[] {
  if (!value || typeof value !== 'object') return [prefix];
  return Object.entries(value).flatMap(([key, child]) =>
    flattenKeys(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe('internationalization', () => {
  it('keeps every locale catalog structurally complete', () => {
    const expectedKeys = flattenKeys(en).sort();
    for (const catalog of [zhCN, zhTW, de, ja, fr, ko]) {
      expect(flattenKeys(catalog).sort()).toEqual(expectedKeys);
    }
  });

  it('normalizes supported browser locales', () => {
    expect(normalizeLocale('zh-Hans-CN')).toBe('zh-CN');
    expect(normalizeLocale('zh-Hant-HK')).toBe('zh-TW');
    expect(normalizeLocale('de-DE')).toBe('de');
    expect(normalizeLocale('ja-JP')).toBe('ja');
    expect(normalizeLocale('es-ES')).toBe('en');
    expect(supportedLocales).toHaveLength(7);
  });
});
