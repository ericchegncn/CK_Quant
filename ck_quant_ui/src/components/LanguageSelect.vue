<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import {
  nativeLocaleNames,
  setLocale,
  supportedLocales,
  type SupportedLocale,
} from '@/i18n';

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });

const settingsStore = useSettingsStore();
const { t } = useI18n();

const languageItems = supportedLocales.map((locale) => ({
  label: nativeLocaleNames[locale],
  value: locale,
}));

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
