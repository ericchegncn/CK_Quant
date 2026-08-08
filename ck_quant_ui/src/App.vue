<script setup lang="ts">
import { setLocale } from '@/i18n';

const settingsStore = useSettingsStore();
const colorStore = useColorStore();
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
      <NavBar />
      <BodyLayout class="grow overflow-auto" />
      <NavFooter />
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
