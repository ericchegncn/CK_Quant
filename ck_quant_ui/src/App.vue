<script setup lang="ts">
import { setLocale } from '@/i18n';

const settingsStore = useSettingsStore();
const colorStore = useColorStore();
const botStore = useBotStore();
// Guests (no configured bot) only reach the showcase page, so the navigation
// chrome is hidden for them.
const isGuest = computed(() => !botStore.hasBots);

onMounted(() => {
  setTimezone(settingsStore.timezone);
  colorStore.updateProfitLossColor();
});
watch(
  () => settingsStore.timezone,
  (tz) => {
    console.log('timezone changed', tz);
    setTimezone(tz);
  },
);
watch(
  () => settingsStore.locale,
  (locale) => setLocale(locale),
  { immediate: true },
);
</script>

<template>
  <UApp>
    <div id="app" class="flex flex-col h-dvh ckq-shell" :style="colorStore.cssVars">
      <NavBar v-if="!isGuest" />
      <BodyLayout class="grow overflow-auto" :class="isGuest ? 'pb-0' : 'md:pb-0 pb-24'" />
      <NavFooter v-if="!isGuest" />
    </div>
  </UApp>
</template>

<style scoped>
#app {
  font-family:
    Inter,
    ui-rounded,
    'SF Pro Display',
    'SF Pro Text',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
}

/* * {
  outline: 1px solid #f00 !important;
} */
</style>
