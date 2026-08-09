<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { GridItemData } from '@/types';

const botStore = useBotStore();
const { t } = useI18n();

const layoutStore = useLayoutStore();
const currentBreakpoint = ref('');

function breakpointChanged(newBreakpoint: string) {
  // console.log('breakpoint:', newBreakpoint);
  currentBreakpoint.value = newBreakpoint;
}
const isResizableLayout = computed(() =>
  ['', 'sm', 'md', 'lg', 'xl'].includes(currentBreakpoint.value),
);
const isLayoutLocked = computed(() => {
  return layoutStore.layoutLocked || !isResizableLayout.value;
});

// 一卡片一屏：卡片高度 = 视口高度（- 导航栏）
// 关键：vue-grid-layout 每行实际占用 = ROW_HEIGHT + MARGIN = 70px
const ROW_HEIGHT = 50;
const NAV_HEIGHT = 120; // 顶部导航 + 页头高度
const MARGIN = 20; // 卡片间距
const ROW_STEP = ROW_HEIGHT + MARGIN; // 每行实际占 70px
// 可用视口高度对应的行数（每行 70px），保证大卡片底部在屏幕内
const viewportRows = ref(Math.max(6, Math.floor((window.innerHeight - NAV_HEIGHT) / ROW_STEP)));
const viewportWidth = ref(window.innerWidth);
// The merged overview stays compact on desktop and becomes a scroll-friendly single card on mobile.
const overviewRows = computed(() =>
  Math.max(viewportRows.value, viewportWidth.value < 768 ? 22 : 10),
);
function updateViewportRows() {
  viewportRows.value = Math.max(6, Math.floor((window.innerHeight - NAV_HEIGHT) / ROW_STEP));
  viewportWidth.value = window.innerWidth;
}
onMounted(() => {
  window.addEventListener('resize', updateViewportRows);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportRows);
});

const gridLayoutData = computed((): GridItemData[] => {
  // The first card combines bot comparison, /profit metrics and the cumulative profit curve.
  // Remaining cards keep the one-card-per-viewport layout.
  const order: { i: number; w: number }[] = [
    { i: DashboardLayout.botComparison, w: 12 },
    { i: DashboardLayout.allOpenTrades, w: 12 },
    { i: DashboardLayout.allClosedTrades, w: 12 },
    { i: DashboardLayout.tradesLogChart, w: 12 },
    { i: DashboardLayout.dailyChart, w: 12 },
    { i: DashboardLayout.walletHistoryChart, w: 12 },
    { i: DashboardLayout.profitDistributionChart, w: 12 },
  ];
  return order.map((item, idx) => {
    if (idx === 0) {
      return { i: item.i, x: 0, y: 0, w: item.w, h: overviewRows.value };
    }
    return {
      i: item.i,
      x: 0,
      y: overviewRows.value + (idx - 1) * viewportRows.value,
      w: item.w,
      h: viewportRows.value,
    };
  });
});

function layoutUpdatedEvent(newLayout) {
  if (isResizableLayout.value) {
    console.log('newlayout', newLayout);
    console.log('saving dashboard');
    layoutStore.dashboardLayout = newLayout;
  }
}

const gridLayoutDaily = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.dailyChart);
});

const gridLayoutBotComparison = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.botComparison);
});

const gridLayoutAllOpenTrades = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.allOpenTrades);
});
const gridLayoutAllClosedTrades = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.allClosedTrades);
});

const gridLayoutWalletHistory = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.walletHistoryChart);
});

const gridLayoutProfitDistribution = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.profitDistributionChart);
});
const gridLayoutTradesLogChart = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.tradesLogChart);
});

const responsiveGridLayouts = computed(() => {
  return {
    sm: gridLayoutData.value,
  };
});

onMounted(async () => {
  botStore.allGetDaily({ timescale: 30 });
  // botStore.activeBot.getTrades();
  botStore.activeBot.getOpenTrades();
  botStore.activeBot.getProfit();
});
</script>

<template>
  <GridLayout
    class="h-full w-full"
    style="width: 100%; padding: 1px"
    :row-height="50"
    :layout="gridLayoutData"
    :vertical-compact="false"
    :margin="[20, 20]"
    :responsive-layouts="responsiveGridLayouts"
    :is-resizable="!isLayoutLocked"
    :is-draggable="!isLayoutLocked"
    :responsive="true"
    :prevent-collision="true"
    :cols="{ lg: 12, md: 12, sm: 12, xs: 12, xxs: 12 }"
    :col-num="12"
    @layout-updated="layoutUpdatedEvent"
    @update:breakpoint="breakpointChanged"
  >
    <template #default="{ gridItemProps }">
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutDaily.i"
        :x="gridLayoutDaily.x"
        :y="gridLayoutDaily.y"
        :w="gridLayoutDaily.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer
          :header="
            `${t('workspace.profitOverTime')} ${botStore.botCount > 1 ? t('workspace.combined') : ''}`.trim()
          "
        >
          <PeriodBreakdown multi-bot-view />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutBotComparison.i"
        :x="gridLayoutBotComparison.x"
        :y="gridLayoutBotComparison.y"
        :w="gridLayoutBotComparison.w"
        :h="overviewRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer :header="t('workspace.dashboardOverview')">
          <BotDashboardOverview />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutAllOpenTrades.i"
        :x="gridLayoutAllOpenTrades.x"
        :y="gridLayoutAllOpenTrades.y"
        :w="gridLayoutAllOpenTrades.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer
          :header="t('workspace.openTrades')"
          :info-text="t('workspace.openTradesInfo')"
        >
          <TradeList active-trades :trades="botStore.allOpenTradesSelectedBots" multi-bot-view />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutWalletHistory.i"
        :x="gridLayoutWalletHistory.x"
        :y="gridLayoutWalletHistory.y"
        :w="gridLayoutWalletHistory.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer :header="t('workspace.walletHistory')">
          <WalletHistoryChart :wallet-data="botStore.allBalanceHistory" :show-title="false" />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutAllClosedTrades.i"
        :x="gridLayoutAllClosedTrades.x"
        :y="gridLayoutAllClosedTrades.y"
        :w="gridLayoutAllClosedTrades.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer
          :header="t('workspace.closedTrades')"
          :info-text="t('workspace.closedTradesInfo')"
        >
          <TradeList
            :active-trades="false"
            show-filter
            :trades="botStore.allClosedTradesSelectedBots"
            multi-bot-view
          />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutProfitDistribution.i"
        :x="gridLayoutProfitDistribution.x"
        :y="gridLayoutProfitDistribution.y"
        :w="gridLayoutProfitDistribution.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer :header="t('workspace.profitDistribution')">
          <ProfitDistributionChart :trades="botStore.allTradesSelectedBots" :show-title="false" />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutTradesLogChart.i"
        :x="gridLayoutTradesLogChart.x"
        :y="gridLayoutTradesLogChart.y"
        :w="gridLayoutTradesLogChart.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer :header="t('workspace.tradesLog')">
          <TradesLogChart :trades="botStore.allTradesSelectedBots" :show-title="false" />
        </DraggableContainer>
      </GridItem>
    </template>
  </GridLayout>
</template>
