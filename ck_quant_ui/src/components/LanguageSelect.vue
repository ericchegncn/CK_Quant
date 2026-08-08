<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import { setLocale, supportedLocales, type SupportedLocale } from '@/i18n';

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });

const settingsStore = useSettingsStore();
const { t } = useI18n();

const languageItems = computed(() => [
  { label: t('language.zhCN'), value: 'zh-CN' },
  { label: t('language.zhTW'), value: 'zh-TW' },
  { label: t('language.en'), value: 'en' },
  { label: t('language.de'), value: 'de' },
  { label: t('language.ja'), value: 'ja' },
  { label: t('language.fr'), value: 'fr' },
  { label: t('language.ko'), value: 'ko' },
]);

function updateLanguage(value: string): void {
  if (supportedLocales.includes(value as SupportedLocale)) {
    settingsStore.locale = value as SupportedLocale;
    setLocale(settingsStore.locale);
  }
}
</script>

<template>
  <USelect
    :model-value="settingsStore.locale"
    :items="languageItems"
    value-key="value"
    :aria-label="t('language.label')"
    :class="compact ? 'w-32' : 'w-full'"
    @update:model-value="updateLanguage"
  />
</template>
