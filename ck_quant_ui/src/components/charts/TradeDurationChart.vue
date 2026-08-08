<script setup lang="ts">
import ECharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';
import type { ClosedTrade } from '@/types';
import type { EChartsOption } from 'echarts';
import { format as echartsFormat } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BoxplotChart, ScatterChart } from 'echarts/charts';
import {
  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
  VisualMapComponent,
} from 'echarts/components';

const props = withDefaults(
  defineProps<{
    trades: ClosedTrade[];
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);

const settingsStore = useSettingsStore();
const { t } = useI18n();

use([
  DatasetComponent,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  TransformComponent,
  BoxplotChart,
  CanvasRenderer,
  VisualMapComponent,
  ScatterChart,
]);

const allTrades = computed(() => {
  return props.trades.map((trade) => {
    // Convert timestamp difference to minutes (timestamps are in milliseconds)
    return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
  });
});

const winningTrades = computed(() => {
  return props.trades
    .filter((trade) => (trade.profit_ratio ?? 0) > 0)
    .map((trade) => {
      return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
    });
});

const losingTrades = computed(() => {
  return props.trades
    .filter((trade) => (trade.profit_ratio ?? 0) <= 0)
    .map((trade) => {
      return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
    });
});

const chartOptions = computed((): EChartsOption => {
  const allTradesLabel = t('workspace.allTrades');
  const winningTradesLabel = t('workspace.winningTrades');
  const losingTradesLabel = t('workspace.losingTrades');
  return {
    title: {
      text: t('workspace.tradeDurations'),
      left: 'center',
      show: props.showTitle,
    },
    backgroundColor: 'rgba(0, 0, 0, 0)',
    dataset: [
      {
        id: 'allTrades',
        source: [allTrades.value, winningTrades.value, losingTrades.value],
      },
      {
        id: 'allTradesBoxplot',
        fromDatasetId: 'allTrades',
        transform: {
          type: 'boxplot',

          config: {
            itemNameFormatter: (params) => {
              if (params.value === 0) {
                return allTradesLabel;
              } else if (params.value === 1) {
                return winningTradesLabel;
              } else if (params.value === 2) {
                return losingTradesLabel;
              }
            },
          },
        },
      },
      {
        id: 'outlier',
        fromDatasetIndex: 1,
        fromTransformResult: 1,
      },
    ],
    xAxis: {
      type: 'category',
      show: true,
      // data: ['All Trades', 'Winning Trades', 'Losing Trades'],
    },
    yAxis: [
      {
        type: 'value',
        name: t('workspace.tradeDuration'),
        splitArea: {
          show: true,
        },
        axisLabel: {
          formatter: formatDuration,
        },
      },
    ],
    tooltip: {
      formatter: (params) => {
        if (params.seriesType === 'boxplot') {
          const statistics = params.data;
          return `
            <div>${echartsFormat.encodeHTML(params.name)}</div>
            <div>${t('workspace.minimum')}: ${echartsFormat.encodeHTML(formatDuration(statistics[1]))}</div>
            <div>Q1: ${echartsFormat.encodeHTML(formatDuration(statistics[2]))}</div>
            <div>${t('workspace.median')}: ${echartsFormat.encodeHTML(formatDuration(statistics[3]))}</div>
            <div>Q3: ${echartsFormat.encodeHTML(formatDuration(statistics[4]))}</div>
            <div>${t('workspace.maximum')}: ${echartsFormat.encodeHTML(formatDuration(statistics[5]))}</div>
          `;
        }
        return '';
      },
    },
    visualMap: [
      {
        type: 'piecewise',
        show: false,
        dimension: 0,
        pieces: [
          {
            min: 0,
            max: 0,
            label: allTradesLabel,
            color: '#5470c6',
          },
          {
            min: 1,
            max: 1,
            label: winningTradesLabel,
            color: '#12bb7b',
          },
          {
            min: 2,
            max: 2,
            label: losingTradesLabel,
            color: '#ef5350',
          },
        ],
      },
    ],
    series: [
      {
        name: t('workspace.tradeDurations'),
        type: 'boxplot',
        datasetId: 'allTradesBoxplot',
        colorBy: 'data',
        // itemStyle: {
        //   color: '#b8c5f2',
        // },
      },
      {
        name: t('workspace.outlier'),
        type: 'scatter',
        datasetId: 'outlier',
      },
    ],
  };
});

// Helper function to format duration in human-readable format
function formatDuration(minutes: number): string {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours}h ${mins}m`;
  }
  return `${Math.floor(minutes)}m`;
}
</script>

<template>
  <!-- {{ chartData }} -->
  <ECharts
    v-if="trades.length > 0"
    :option="chartOptions"
    autoresize
    :theme="settingsStore.chartTheme"
  />
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
