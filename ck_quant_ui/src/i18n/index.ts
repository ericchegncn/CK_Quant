import { createI18n } from 'vue-i18n';

import de from './locales/de';
import en from './locales/en';
import fr from './locales/fr';
import ja from './locales/ja';
import ko from './locales/ko';
import zhCN from './locales/zh-CN';
import zhTW from './locales/zh-TW';

export const supportedLocales = ['zh-CN', 'zh-TW', 'en', 'de', 'ja', 'fr', 'ko'] as const;
export type SupportedLocale = (typeof supportedLocales)[number];

const messages = { 'zh-CN': zhCN, 'zh-TW': zhTW, en, de, ja, fr, ko };

export function normalizeLocale(locale?: string | null): SupportedLocale {
  const normalized = (locale ?? '').replace('_', '-').toLowerCase();
  if (
    normalized.startsWith('zh-tw') ||
    normalized.startsWith('zh-hk') ||
    normalized.startsWith('zh-hant')
  )
    return 'zh-TW';
  if (normalized.startsWith('zh')) return 'zh-CN';
  const match = supportedLocales.find((item) => normalized.startsWith(item.toLowerCase()));
  return match ?? 'en';
}

export function detectLocale(): SupportedLocale {
  const stored = localStorage.getItem('ckqLocale');
  if (stored) return normalizeLocale(stored);
  return normalizeLocale(navigator.languages?.[0] ?? navigator.language);
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages,
});

export function setLocale(locale: SupportedLocale): void {
  i18n.global.locale.value = locale;
  localStorage.setItem('ckqLocale', locale);
  document.documentElement.lang = locale;
}

setLocale(i18n.global.locale.value);
