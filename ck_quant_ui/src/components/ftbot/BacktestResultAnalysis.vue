<script setup lang="ts">
import type { StrategyBacktestResult } from '@/types';
import { useI18n } from 'vue-i18n';

const props = defineProps<{
  backtestResult: StrategyBacktestResult;
}>();
const { t } = useI18n();

const backtestResultStats = computed(() => {
  const tmp = localizeBacktestRows(generateBacktestMetricRows(props.backtestResult), t);
  return formatObjectForTable({ value: tmp }, 'metric');
});

const backtestResultSettings = computed(() => {
  // Transpose Result into readable format
  const tmp = localizeBacktestRows(generateBacktestSettingRows(props.backtestResult), t);

  return formatObjectForTable({ value: tmp }, 'setting');
});
</script>

<template>
  <div class="px-0 w-full">
    <div class="flex justify-center">
      <h3 class="font-bold text-2xl mb-2">
        {{ t('research.resultFor', { strategy: backtestResult.strategy_name }) }}
      </h3>
    </div>

    <div class="flex flex-col text-start ms-0 me-2 gap-2">
      <div class="flex flex-col xl:flex-row">
        <div class="px-0 px-xl-0 pe-xl-1 grow">
          <DraggableContainer :header="t('research.strategySettings')">
            <UTable
              :data="backtestResultSettings"
              :columns="[
                { accessorKey: 'setting', header: t('research.setting') },
                { accessorKey: 'value', header: t('research.value') },
              ]"
            />
          </DraggableContainer>
        </div>
        <div class="px-0 xl:px-0 pt-2 xl:pt-0 xl:ps-1 grow">
          <DraggableContainer :header="t('research.metrics')">
            <UTable
              :data="backtestResultStats"
              :columns="[
                { accessorKey: 'metric', header: t('research.metric') },
                { accessorKey: 'value', header: t('research.value') },
              ]"
            />
          </DraggableContainer>
        </div>
      </div>
      <BacktestResultTablePer
        :title="t('research.resultsPerEntryTag')"
        :results="backtestResult.results_per_enter_tag"
        :stake-currency="backtestResult.stake_currency"
        :key-header="t('research.entryTag')"
        :stake-currency-decimals="backtestResult.stake_currency_decimals"
      />

      <BacktestResultTablePer
        :title="t('research.resultsPerExitReason')"
        :results="backtestResult.exit_reason_summary ?? []"
        :stake-currency="backtestResult.stake_currency"
        :key-header="t('research.exitReason')"
        :stake-currency-decimals="backtestResult.stake_currency_decimals"
      />

      <BacktestResultTablePer
        v-if="backtestResult.mix_tag_stats"
        :title="t('research.resultsMixedTag')"
        :results="backtestResult.mix_tag_stats ?? []"
        :stake-currency="backtestResult.stake_currency"
        :key-headers="[t('research.entryTag'), t('research.exitTag')]"
        :stake-currency-decimals="backtestResult.stake_currency_decimals"
      />

      <BacktestResultTablePer
        :title="t('research.resultsPerPair')"
        :results="backtestResult.results_per_pair"
        :stake-currency="backtestResult.stake_currency"
        :key-header="t('research.pair')"
        :stake-currency-decimals="backtestResult.stake_currency_decimals"
      />
      <DraggableContainer v-if="backtestResult.periodic_breakdown" :header="t('research.periodicBreakdown')">
        <BacktestResultPeriodBreakdown :periodic-breakdown="backtestResult.periodic_breakdown">
        </BacktestResultPeriodBreakdown>
      </DraggableContainer>

      <DraggableContainer :header="t('research.singleTrades')">
        <TradeList
          :trades="backtestResult.trades"
          :show-filter="true"
          :stake-currency="backtestResult.stake_currency"
        />
      </DraggableContainer>
    </div>
  </div>
</template>
