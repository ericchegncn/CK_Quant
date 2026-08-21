<script setup lang="ts">
import type { LookaheadAnalysisPayload } from '@/types';
import { useI18n } from 'vue-i18n';

const props = defineProps<{
  running: boolean;
}>();

const emit = defineEmits<{
  start: [payload: LookaheadAnalysisPayload];
}>();

const botStore = useBotStore();
const btStore = useBtStore();
const { t } = useI18n();

const canStart = computed(
  () => !!btStore.strategy && !props.running && botStore.activeBot.canRunBacktest,
);

function emitStart() {
  const payload: LookaheadAnalysisPayload = {
    strategy: btStore.strategy,
    minimum_trade_amount: btStore.lookaheadMinTradeAmount,
    targeted_trade_amount: btStore.lookaheadTargetedTradeAmount,
    lookahead_allow_limit_orders: btStore.lookaheadAllowLimitOrders,
  };
  if (btStore.selectedTimeframe) {
    payload.timeframe = btStore.selectedTimeframe;
  }
  if (btStore.timerange) {
    payload.timerange = btStore.timerange;
  }
  emit('start', payload);
}

onMounted(() => {
  if (botStore.activeBot.strategyList.length === 0) {
    botStore.activeBot.getStrategyList();
  }
});
</script>

<template>
  <div>
    <UAlert
      color="info"
      class="mb-3 py-2"
      :title="t('research.lookaheadAnalysis')"
      :description="t('research.lookaheadDescription')"
    />

    <div class="flex flex-col gap-3">
      <div>
        <span class="font-bold">{{ t('research.strategy') }}</span>
        <StrategySelect v-model="btStore.strategy" />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 items-center">
        <label for="lookahead-timeframe" class="md:text-right">{{ t('research.timeframe') }}:</label>
        <TimeframeSelect id="lookahead-timeframe" v-model="btStore.selectedTimeframe" />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 items-center">
        <div class="flex items-center gap-2 md:justify-end">
          <label for="lookahead-minimum-trade-amount" class="font-bold"
            >{{ t('research.minimumTradeAmount') }}:</label
          >
          <InfoBox
            :hint="t('research.minimumTradeAmountHint')"
          />
        </div>
        <UInput
          id="lookahead-minimum-trade-amount"
          v-model.number="btStore.lookaheadMinTradeAmount"
          type="number"
          min="1"
          class="w-full"
        />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 items-center">
        <div class="flex items-center gap-2 md:justify-end">
          <label for="lookahead-targeted-trade-amount" class="font-bold"
            >{{ t('research.targetedTradeAmount') }}:</label
          >
          <InfoBox
            :hint="t('research.targetedTradeAmountHint')"
          />
        </div>
        <UInput
          id="lookahead-targeted-trade-amount"
          v-model.number="btStore.lookaheadTargetedTradeAmount"
          type="number"
          min="1"
          class="w-full"
        />
      </div>

      <div class="flex items-center gap-2">
        <UCheckbox id="lookahead-allow-limit-orders" v-model="btStore.lookaheadAllowLimitOrders" />
        <label for="lookahead-allow-limit-orders">{{ t('research.allowLimitOrders') }}</label>
        <InfoBox
          :hint="t('research.allowLimitOrdersHint')"
        />
      </div>

      <TimeRangeSelect v-model="btStore.timerange" class="mx-auto mt-1" />

      <div class="flex justify-center mt-2">
        <UButton
          icon="i-mdi-play"
          variant="solid"
          :loading="running"
          :disabled="!canStart"
          @click="emitStart"
        >
          {{ t('research.startLookaheadAnalysis') }}
        </UButton>
      </div>
    </div>
  </div>
</template>
