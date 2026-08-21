<script setup lang="ts">
import type { PeriodicBreakdown } from '@/types';
import { useI18n } from 'vue-i18n';
import type { TableColumn } from '@nuxt/ui';

const props = defineProps<{
  periodicBreakdown: PeriodicBreakdown;
}>();
const { t } = useI18n();

const periodicBreakdownSelections = computed(() => {
  const res = [
    { value: 'day', label: t('research.days') },
    { value: 'week', label: t('research.weeks') },
    { value: 'month', label: t('research.months') },
  ];
  if (props.periodicBreakdown.year) {
    res.push({ value: 'year', label: t('research.years') });
  }
  if (props.periodicBreakdown.weekday) {
    res.push({ value: 'weekday', label: t('research.weekday') });
  }

  return res;
});

const periodicBreakdownPeriod = ref<string>('month');

type PeriodRow = {
  date: string;
  trades?: number;
  profit_abs?: number;
  profit_factor?: number;
  wins?: number;
  draws?: number;
  losses?: number;
  loses?: number;
};

const columns = computed<TableColumn<PeriodRow>[]>(() => [
  { accessorKey: 'date', header: t('research.date') },
  { accessorKey: 'trades', header: t('research.trades') },
  { accessorKey: 'profit_abs', header: t('research.totalProfit') },
  { accessorKey: 'profit_factor', header: t('research.profitFactor') },
  { accessorKey: 'wins', header: t('research.wins') },
  { accessorKey: 'draws', header: t('research.draws') },
  { accessorKey: 'losses', header: t('research.losses') },
  { id: 'win_rate', header: t('research.winRate') },
]);
</script>

<template>
  <USegmentedControl
    v-model="periodicBreakdownPeriod"
    :items="periodicBreakdownSelections"
    value-key="value"
    size="md"
    class="m-2"
  ></USegmentedControl>
  <UTable :data="periodicBreakdown[periodicBreakdownPeriod]" :columns="columns">
    <template #trades-cell="{ row }">
      {{ row.original.trades ?? 'N/A' }}
    </template>
    <template #profit_abs-cell="{ row }">
      {{ formatNumber(row.original.profit_abs, 2) }}
    </template>
    <template #profit_factor-cell="{ row }">
      {{ formatPrice(row.original.profit_factor ?? null, 2) }}
    </template>
    <template #losses-cell="{ row }">
      {{ row.original.loses ?? row.original.losses ?? 'N/A' }}
    </template>
    <template #win_rate-cell="{ row }">
      {{
        formatPercent(
          row.original.wins! /
            (row.original.wins! +
              row.original.draws! +
              (row.original.loses ?? row.original.losses ?? 0)),
          2,
        )
      }}
    </template>
  </UTable>
</template>
