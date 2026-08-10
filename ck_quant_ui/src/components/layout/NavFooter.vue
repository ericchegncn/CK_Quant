<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>

<template>
  <footer class="md:hidden ckq-bottom-nav">
    <!-- 浮动底部导航：始终显示（手机视口） -->
    <div class="flex gap-2 justify-between px-2">
      <UButton
        icon-pos="top"
        variant="link"
        active-class="underline"
        class="flex flex-col gap-1"
        to="/open_trades"
        :label="t('nav.trades')"
        icon="mdi:folder-open"
      />
      <UButton
        icon-pos="top"
        variant="link"
        active-class="underline"
        class="flex flex-col gap-1"
        to="/trade_history"
        :label="t('nav.history')"
        icon="mdi:folder-lock"
      />
      <UButton
        icon-pos="top"
        variant="link"
        class="flex flex-col gap-1"
        active-class="underline"
        to="/pairlist"
        :label="t('nav.pairlist')"
        icon="mdi:format-list-group"
      />
      <UButton
        icon-pos="top"
        variant="link"
        active-class="underline"
        class="flex flex-col gap-1"
        to="/balance"
        :label="t('nav.balance')"
        icon="mdi:bank"
      />
      <UButton
        icon-pos="top"
        variant="link"
        class="flex flex-col gap-1"
        active-class="underline"
        to="/dashboard"
        :label="t('nav.dashboard')"
        icon="mdi:view-dashboard-outline"
      />
    </div>
  </footer>
</template>
