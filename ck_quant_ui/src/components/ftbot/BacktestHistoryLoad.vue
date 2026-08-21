<script setup lang="ts">
import type { BacktestHistoryEntry } from '@/types';
import { useI18n } from 'vue-i18n';
import type { TableColumn } from '@nuxt/ui';
import type { TableMeta, Row } from '@tanstack/vue-table';

const botStore = useBotStore();
const { confirm } = useConfirmBox();
const { t } = useI18n();
const filterText = ref('');
const filterTextDebounced = refDebounced(filterText, 350, { maxWait: 1000 });

onMounted(() => {
  botStore.activeBot.getBacktestHistory();
});

async function deleteBacktestResult(result: BacktestHistoryEntry) {
  if (
    await confirm({
      title: t('research.deleteResult'),
      message: t('research.deleteResultQuestion', { filename: result.filename }),
    })
  ) {
    botStore.activeBot.deleteBacktestHistoryResult(result);
  }
}

const filteredList = computed(() =>
  botStore.activeBot.backtestHistoryList.filter(
    (r) =>
      r.filename.toLowerCase().includes(filterTextDebounced.value.toLowerCase()) ||
      r.strategy.toLowerCase().includes(filterTextDebounced.value.toLowerCase()),
  ),
);
const columns = computed<TableColumn<BacktestHistoryEntry>[]>(() => [
  { accessorKey: 'strategy', header: t('research.strategy') },
  { accessorKey: 'timeframe', header: t('research.details') },
  { accessorKey: 'backtest_start_time', header: t('research.backtestTime') },
  { accessorKey: 'filename', header: t('research.filename') },
  { id: 'actions', header: t('research.actions') },
]);

function isRowLoaded(row: Row<BacktestHistoryEntry>) {
  return row.original.run_id in botStore.activeBot.backtestHistory;
}

const meta: TableMeta<BacktestHistoryEntry> = {
  class: {
    tr: (row: Row<BacktestHistoryEntry>) => {
      if (isRowLoaded(row)) {
        return 'dark:bg-mute1d dark:bg-mist-700 bg-mist-200 cursor-not-allowed';
      }
      return '';
    },
  },
};
</script>

<template>
  <div>
    <UButton
      class="float-end"
      :title="t('research.refresh')"
      :aria-label="t('research.refresh')"
      variant="outline"
      color="neutral"
      icon="mdi:refresh"
      @click="botStore.activeBot.getBacktestHistory"
    />
    <p>
      {{ t('research.historicResultsHint') }}
    </p>
    <div v-if="botStore.activeBot.backtestHistoryList.length > 0" class="flex align-center">
      <UInput
        id="trade-filter"
        v-model="filterText"
        type="text"
        :placeholder="t('research.filterResults')"
        :title="t('research.filterResults')"
      />
    </div>
    <UTable
      v-if="botStore.activeBot.backtestHistoryList.length > 0"
      class="mt-2 h-[80dvh]"
      :data="filteredList"
      :columns="columns"
      :meta="meta"
      :virtualize="{ estimateSize: 38, overscan: 12 }"
      sticky
      @select="(e, row) => botStore.activeBot.getBacktestHistoryResult(row.original)"
    >
      <template #timeframe-cell="{ row }">
        <strong>{{ row.original.timeframe }}</strong>
        <span v-if="row.original.backtest_start_ts && row.original.backtest_end_ts" class="ms-1">
          {{ timestampToTimeRangeString(row.original.backtest_start_ts * 1000) }}-{{
            timestampToTimeRangeString(row.original.backtest_end_ts * 1000)
          }}</span
        >
      </template>
      <template #backtest_start_time-cell="{ row }">
        <DateTimeTZ :date="row.original.backtest_start_time * 1000" />
      </template>
      <template #actions-cell="{ row }">
        <div class="flex items-center gap-1">
          <InfoBox
            v-if="botStore.activeBot.botFeatures.backtestSetNotes"
            :class="row.original.notes ? 'opacity-100' : 'opacity-0'"
            :hint="row.original.notes ?? ''"
          ></InfoBox>
          <UButton
            v-if="botStore.activeBot.botFeatures.backtestDelete && !isRowLoaded(row)"
            size="sm"
            variant="solid"
            :title="t('research.loadThisResult')"
            color="primary"
            icon="mdi:arrow-right"
            :disabled="isRowLoaded(row)"
            @click.stop="botStore.activeBot.getBacktestHistoryResult(row.original)"
          />
          <UButton
            v-if="isRowLoaded(row)"
            :title="t('research.unloadThisResult')"
            icon="mdi:close"
            size="sm"
            variant="solid"
            color="success"
            @click.stop="botStore.activeBot.removeBacktestResultFromMemory(row.original.run_id)"
          />
          <UButton
            v-if="botStore.activeBot.botFeatures.backtestDelete"
            size="sm"
            color="neutral"
            :title="t('research.deleteThisResult')"
            icon="mdi:delete"
            :disabled="isRowLoaded(row)"
            @click.stop="deleteBacktestResult(row.original)"
          />
        </div>
      </template>
    </UTable>
  </div>
</template>
