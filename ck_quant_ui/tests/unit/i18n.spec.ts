import { describe, expect, it } from 'vitest';

import { nativeLocaleNames, normalizeLocale, supportedLocales } from '@/i18n';
import de from '@/i18n/locales/de';
import en from '@/i18n/locales/en';
import fr from '@/i18n/locales/fr';
import ja from '@/i18n/locales/ja';
import ko from '@/i18n/locales/ko';
import zhCN from '@/i18n/locales/zh-CN';
import zhTW from '@/i18n/locales/zh-TW';
import { localizePairlistText } from '@/i18n/pairlistText';
import {
  localizeJobCategory,
  localizeJobDescription,
  localizeJobStatus,
} from '@/i18n/backgroundJobText';

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

  it('keeps research interpolation variables intact in every locale', () => {
    const catalogs = [zhCN, zhTW, de, ja, fr, ko];
    const placeholders = (value: string) => value.match(/\{[A-Za-z][A-Za-z0-9]*\}/g)?.sort() ?? [];

    for (const catalog of catalogs) {
      for (const key of Object.keys(en.research) as (keyof typeof en.research)[]) {
        expect(placeholders(catalog.research[key]), `${key} placeholders`).toEqual(
          placeholders(en.research[key]),
        );
      }
    }
  });

  it('localizes representative dashboard, trade, and chart labels', () => {
    for (const catalog of [zhCN, zhTW, de, ja, fr, ko]) {
      for (const key of [
        'openTrades',
        'botComparison',
        'dashboardOverview',
        'forceExitingTrade',
        'tradeDurations',
        'plotConfigName',
      ] as const) {
        expect(catalog.workspace[key]).not.toBe(en.workspace[key]);
      }
    }
  });

  it('localizes the research and pairlist workspace in simplified Chinese', () => {
    for (const key of [
      'backtestingParameters',
      'downloadingData',
      'lookaheadAnalysis',
      'recursiveAnalysis',
      'availablePairlists',
      'maxDrawdown',
    ] as const) {
      expect(zhCN.research[key]).not.toBe(en.research[key]);
    }
    expect(
      localizePairlistText('Provides dynamic pair list based on trade volumes.', 'zh-CN'),
    ).toBe('根据交易成交量动态生成交易对列表。');
  });

  it('localizes dynamic background-job text without losing parameters', () => {
    const translate = (key: string, values?: Record<string, string | number>) => {
      const message = key.split('.').reduce<unknown>((catalog, part) => {
        if (!catalog || typeof catalog !== 'object') return undefined;
        return (catalog as Record<string, unknown>)[part];
      }, zhCN);
      return String(message).replace(/\{(\w+)\}/g, (_, name: string) =>
        String(values?.[name] ?? ''),
      );
    };

    expect(localizeJobCategory('backtest', translate)).toBe('回测');
    expect(localizeJobStatus('running', translate)).toBe('运行中');
    expect(localizeJobDescription('Startup candle 1999', translate)).toBe('启动 K 线 1999');
    expect(localizeJobDescription('Analyzing trades', translate)).toBe('正在分析交易');
    expect(localizeJobDescription('Downloading ETH/USDT:USDT', translate)).toBe(
      '正在下载 ETH/USDT:USDT',
    );
  });

  it('localizes research and pairlist content in every non-English locale', () => {
    for (const [locale, catalog] of [
      ['zh-TW', zhTW],
      ['de', de],
      ['ja', ja],
      ['fr', fr],
      ['ko', ko],
    ] as const) {
      expect(catalog.research.downloadingData).not.toBe(en.research.downloadingData);
      expect(catalog.research.lookaheadDescription).not.toBe(en.research.lookaheadDescription);
      expect(catalog.research.availablePairlists).not.toBe(en.research.availablePairlists);
      expect(
        localizePairlistText('Provides dynamic pair list based on trade volumes.', locale),
      ).not.toBe('Provides dynamic pair list based on trade volumes.');
    }
  });
});
