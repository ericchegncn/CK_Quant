<script setup lang="ts">
import type { BacktestFreqAIInput } from '@/types';
import { useI18n } from 'vue-i18n';

const freqAI = defineModel<BacktestFreqAIInput>({ required: true });
const { t } = useI18n();
</script>

<template>
  <div class="flex justify-end items-center">
    <span class="me-2">{{ t('research.enableFreqAI') }}:</span>
    <InfoBox
      :hint="t('research.freqAIHint')"
    />
  </div>
  <BaseCheckbox id="enable-freqai" v-model="freqAI.enabled"></BaseCheckbox>

  <template v-if="freqAI.enabled">
    <label for="freqai-identifier">{{ t('research.freqAIIdentifier') }}:</label>
    <UInput
      id="freqai-identifier"
      v-model="freqAI.identifier"
      :placeholder="t('research.useConfigDefault')"
    ></UInput>
  </template>
  <template v-if="freqAI.enabled">
    <label for="freqai-model">{{ t('research.freqAIModel') }}:</label>
    <FreqaiModelSelect id="freqai-model" v-model="freqAI.model"></FreqaiModelSelect>
  </template>
</template>
