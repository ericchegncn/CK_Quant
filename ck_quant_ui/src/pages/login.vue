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
  <div class="max-w-xl mx-auto p-4 my-5">
    <div class="mb-3 ml-auto max-w-52">
      <LanguageSelect />
    </div>
    <DraggableContainer :header="t('login.pageTitle')" class="px-4 py-2">
      <BotLogin />
    </DraggableContainer>
  </div>
</template>
