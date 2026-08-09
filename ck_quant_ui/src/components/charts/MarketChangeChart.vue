<script setup lang="ts">
import ECharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';
// import { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  CalendarComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  TransformComponent,
} from 'echarts/components';
import { registerTransform } from 'echarts';

import type { BacktestMarketChange } from '@/types';
import type { EChartsOption } from 'echarts';

use([
  LineChart,
  CalendarComponent,
  CanvasRenderer,
  GridComponent,
  DatasetComponent,
  DataZoomComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  TransformComponent,
]);

const props = withDefaults(
  defineProps<{
    marketChangeData: BacktestMarketChange | null;
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);

const settingsStore = useSettingsStore();
const { t } = useI18n();

const marketChangeChart = ref(null);
registerTransform(ftEchartsTransforms.multiple);

const marketChangeOptions: ComputedRef<EChartsOption> = computed(() => {
  if (!props.marketChangeData) {
    return {};
  }
  const colDate = props.marketChangeData.columns.findIndex((el) => el === '__date_ts');
  const colRelMean = props.marketChangeData.columns.findIndex((el) => el === 'rel_mean');
  const marketChangeLabel = t('workspace.marketChange');
  return {
    title: {
      text: marketChangeLabel,
      left: 'center',
      show: props.showTitle,
    },
    backgroundColor: 'rgba(0, 0, 0, 0)',
    dataset: [
      {
        source: props.marketChangeData.data,
      },
      {
        transform: {
          type: 'ft:multiple',
          config: { dimension: colRelMean, factor: 100, mode: 'array' },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        label: {
          backgroundColor: '#6a7985',
        },
      },
    },
    grid: {
      ...echartsGridDefault,
    },
    legend: {
      data: [marketChangeLabel],
      right: '5%',
      top: 0,
      selectedMode: false,
    },
    xAxis: [
      {
        type: 'time',
        axisLine: { onZero: false },
        axisTick: { show: true },
        axisLabel: { show: true },
        axisPointer: {
          label: { show: false },
        },
        // position: 'top',
        splitLine: { show: false },
        splitNumber: 20,
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        type: 'value',
        name: marketChangeLabel,
        splitLine: {
          show: false,
        },
        nameRotate: 90,
        nameLocation: 'middle',
        nameGap: 35,
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        bottom: 10,
        start: 0,
        end: 100,
        ...dataZoomPartial,
      },
    ],
    series: [
      {
        type: 'line',
        name: marketChangeLabel,
        showSymbol: false,
        color: settingsStore.chartTheme === 'dark' ? '#c2c2c2' : 'black',
        datasetIndex: 1,
        encode: {
          x: colDate,
          // open, close, low, high
          y: colRelMean,
        },
      },
    ],
  };
});
</script>

<template>
  <ECharts
    v-if="marketChangeData?.data"
    ref="marketChangeChart"
    :option="marketChangeOptions"
    :theme="settingsStore.chartTheme"
    autoresize
  />
</template>

<style lang="css" scoped>
.echarts {
  min-height: 240px;
  height: 100%;
}
</style>
