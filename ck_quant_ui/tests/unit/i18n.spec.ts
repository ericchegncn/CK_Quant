import { describe, expect, it } from 'vitest';

import { nativeLocaleNames, normalizeLocale, supportedLocales } from '@/i18n';
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

  it('uses stable native names in the language picker', () => {
    expect(supportedLocales.map((locale) => nativeLocaleNames[locale])).toEqual([
      '简体中文',
      '繁體中文',
      'English',
      'Deutsch',
      '日本語',
      'Français',
      '한국어',
    ]);
  });

  it('keeps workspace interpolation variables intact in every locale', () => {
    const catalogs = [zhCN, zhTW, de, ja, fr, ko];
    const placeholders = (value: string) => value.match(/\{[A-Za-z][A-Za-z0-9]*\}/g)?.sort() ?? [];

    for (const catalog of catalogs) {
      for (const key of Object.keys(en.workspace) as (keyof typeof en.workspace)[]) {
        expect(placeholders(catalog.workspace[key]), `${key} placeholders`).toEqual(
          placeholders(en.workspace[key]),
        );
      }
    }
  });

  it('localizes representative dashboard, trade, and chart labels', () => {
    for (const catalog of [zhCN, zhTW, de, ja, fr, ko]) {
      for (const key of [
        'openTrades',
        'botComparison',
        'forceExitingTrade',
        'tradeDurations',
        'plotConfigName',
      ] as const) {
        expect(catalog.workspace[key]).not.toBe(en.workspace[key]);
      }
    }
  });
});
