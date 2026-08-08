<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

definePage({
  meta: {
    allowAnonymous: true,
  },
});
</script>

<template>
  <div class="mx-auto max-w-6xl py-6 sm:py-12">
    <section class="ckq-glass-card relative overflow-hidden px-6 py-9 text-left sm:px-10 sm:py-12">
      <div class="absolute -right-24 -top-28 h-72 w-72 rounded-full bg-primary/20 blur-3xl"></div>
      <div class="relative grid items-center gap-8 md:grid-cols-[1fr_auto]">
        <div>
          <div
            class="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary"
          >
            <span
              class="h-2 w-2 rounded-full bg-primary shadow-[0_0_12px_var(--color-brand-400)]"
            ></span>
            {{ t('home.eyebrow') }}
          </div>
          <h1 class="max-w-2xl text-4xl font-semibold tracking-[-0.04em] sm:text-6xl">
            {{ t('home.headlineA') }}<br />
            {{ t('home.headlineB') }}
            <span class="text-primary">{{ t('home.headlineAccent') }}</span>
          </h1>
          <p class="mt-5 max-w-xl text-base leading-7 text-neutral-600 dark:text-neutral-300">
            {{ t('home.description') }}
          </p>
        </div>
        <AppIcon class="h-32 w-32 sm:h-44 sm:w-44" />
      </div>
    </section>

    <section class="mt-5 grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
      <div class="ckq-glass-card p-5 sm:p-7">
        <div class="mb-5 flex items-center justify-between text-left">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              {{ t('home.connections') }}
            </p>
            <h2 class="mt-1 text-xl font-semibold">{{ t('home.tradingBots') }}</h2>
          </div>
          <div class="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">
            {{ t('home.localFirst') }}
          </div>
        </div>
        <BotList />
      </div>

      <div class="ckq-glass-card flex flex-col justify-between p-6 text-left">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            {{ t('home.builtIn') }}
          </p>
          <h2 class="mt-2 text-2xl font-semibold">{{ t('home.executionTitle') }}</h2>
          <p class="mt-3 leading-6 text-neutral-600 dark:text-neutral-300">
            {{ t('home.executionDescription') }}
          </p>
        </div>
        <RouterLink
          to="/dashboard"
          class="mt-8 inline-flex items-center justify-between rounded-2xl bg-primary px-4 py-3 font-semibold text-white shadow-lg shadow-primary/20"
        >
          {{ t('home.openDashboard') }}
          <span aria-hidden="true">→</span>
        </RouterLink>
      </div>
    </section>

    <div class="mt-6 text-sm text-neutral-500 dark:text-neutral-400">
      {{ t('home.basedOn') }}
    </div>
  </div>
</template>
