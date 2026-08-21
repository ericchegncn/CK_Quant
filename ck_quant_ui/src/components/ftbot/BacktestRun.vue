<script setup lang="ts">
import type { BacktestPayload } from '@/types';
import { useI18n } from 'vue-i18n';

const botStore = useBotStore();
const btStore = useBtStore();
const { t } = useI18n();

function clickBacktest() {
  const btPayload: BacktestPayload = {
    strategy: btStore.strategy,
    timerange: btStore.timerange,
    enable_protections: btStore.enableProtections,
  };
  if (btStore.maxOpenTrades) {
    btPayload.max_open_trades = btStore.maxOpenTrades;
  }
  if (btStore.stakeAmountUnlimited) {
    btPayload.stake_amount = 'unlimited';
  } else {
    const stakeAmountLoc = Number(btStore.stakeAmount);
    if (stakeAmountLoc) {
      btPayload.stake_amount = stakeAmountLoc.toString();
    }
  }

  const startingCapitalLoc = Number(btStore.startingCapital);
  if (startingCapitalLoc) {
    btPayload.dry_run_wallet = startingCapitalLoc;
  }

  if (btStore.selectedTimeframe) {
    btPayload.timeframe = btStore.selectedTimeframe;
  }
  if (btStore.selectedDetailTimeframe) {
    btPayload.timeframe_detail = btStore.selectedDetailTimeframe;
  }
  if (!btStore.allowCache) {
    btPayload.backtest_cache = 'none';
  }
  if (btStore.freqAI.enabled) {
    btPayload.freqaimodel = btStore.freqAI.model;
    if (btStore.freqAI.identifier !== '') {
      btPayload.freqai = { identifier: btStore.freqAI.identifier };
    }
  }

  botStore.activeBot.startBacktest(btPayload);
}
</script>

<template>
  <div class="mb-2">
    <span>{{ t('research.strategy') }}</span>
    <StrategySelect v-model="btStore.strategy"></StrategySelect>
  </div>
  <div
    class="grid grid-cols-2 border border-neutral-500 rounded-sm gap-y-2 gap-2 items-center p-1 pt-3"
    :disabled="botStore.activeBot.backtestRunning"
  >
    <!-- Backtesting parameters -->
    <h3 class="font-bold mb-2 col-span-2 text-center">{{ t('research.backtestingParameters') }}</h3>
    <label for="timeframe-select">{{ t('research.timeframe') }}:</label>
    <TimeframeSelect id="timeframe-select" v-model="btStore.selectedTimeframe" />
    <label for="timeframe-detail-select" class="flex justify-end items-center gap-2"
      >{{ t('research.detailTimeframe') }}:
      <InfoBox
        :hint="t('research.detailTimeframeHint')"
      />
    </label>
    <TimeframeSelect
      id="timeframe-detail-select"
      v-model="btStore.selectedDetailTimeframe"
      :below-timeframe="btStore.selectedTimeframe"
    />

    <label for="max-open-trades">{{ t('research.maxOpenTrades') }}:</label>
    <UInputNumber
      id="max-open-trades"
      v-model="btStore.maxOpenTrades"
      :placeholder="t('research.useStrategyDefault')"
      :increment="false"
      :decrement="false"
    ></UInputNumber>
    <label for="starting-capital">{{ t('research.startingCapital') }}:</label>
    <UInputNumber
      id="starting-capital"
      v-model="btStore.startingCapital"
      :placeholder="t('research.useConfigDefault')"
      :increment="false"
      :decrement="false"
      :step="10"
      :min="0"
      :stepSnapping="false"
      :format-options="{
        maximumFractionDigits: 5,
      }"
    ></UInputNumber>
    <label for="stake-amount-bool">{{ t('research.stakeAmount') }}:</label>
    <div class="flex items-center">
      <BaseCheckbox class="basis-1/3" id="stake-amount-bool" v-model="btStore.stakeAmountUnlimited"
        >{{ t('research.unlimitedStake') }}</BaseCheckbox
      >
      <UInputNumber
        id="stake-amount"
        v-model="btStore.stakeAmount"
        :placeholder="t('research.useStrategyDefault')"
        class="w-full"
        :step="10"
        :stepSnapping="false"
        :format-options="{
          maximumFractionDigits: 5,
        }"
        :min="0"
        :increment="false"
        :decrement="false"
        :disabled="btStore.stakeAmountUnlimited"
      ></UInputNumber>
    </div>

    <label for="enable-protections">{{ t('research.enableProtections') }}:</label>
    <BaseCheckbox id="enable-protections" v-model="btStore.enableProtections"></BaseCheckbox>
    <template v-if="botStore.activeBot.botFeatures.backtestFreqAI">
      <label for="enable-cache">{{ t('research.cacheResults') }}:</label>
      <BaseCheckbox id="enable-cache" v-model="btStore.allowCache"></BaseCheckbox>
    </template>

    <FreqAIModelInput
      v-if="botStore.activeBot.botFeatures.backtestFreqAI"
      v-model="btStore.freqAI"
    />

    <USeparator class="col-span-2 my-2" />
    <TimeRangeSelect v-model="btStore.timerange" class="mx-auto mt-2 col-span-2"></TimeRangeSelect>
  </div>

  <h3 class="mt-3 font-bold text-2xl">{{ t('research.backtestingSummary') }}</h3>
  <div class="flex flex-wrap md:flex-nowrap justify-between md:justify-center mt-2">
    <UButton
      id="start-backtest"
      variant="solid"
      icon="mdi:play"
      :disabled="
        !btStore.canRunBacktest ||
        botStore.activeBot.backtestRunning ||
        !botStore.activeBot.canRunBacktest
      "
      class="mx-1"
      @click="clickBacktest"
    >
      {{ t('research.startBacktest') }}
    </UButton>
    <UButton
      color="neutral"
      icon="mdi:refresh"
      :disabled="botStore.activeBot.backtestRunning || !botStore.activeBot.canRunBacktest"
      class="mx-1"
      @click="botStore.activeBot.pollBacktest()"
    >
      {{ t('research.loadBacktestResult') }}
    </UButton>
    <UButton
      color="neutral"
      icon="mdi:stop"
      class="mx-1"
      :disabled="!botStore.activeBot.backtestRunning"
      @click="botStore.activeBot.stopBacktest()"
    >
      {{ t('research.stopBacktest') }}
    </UButton>
    <UButton
      color="neutral"
      class="mx-1"
      icon="mdi:delete"
      :disabled="botStore.activeBot.backtestRunning || !botStore.activeBot.canRunBacktest"
      @click="botStore.activeBot.removeBacktest()"
    >
      {{ t('research.resetBacktest') }}
    </UButton>
  </div>
</template>
<style lang="css" scoped>
label {
  @apply text-right;
}
</style>
