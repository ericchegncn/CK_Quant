<script setup lang="ts">
import type { GridItemData } from '@/types';

const botStore = useBotStore();

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

// 一卡片一屏：卡片高度 = 视口高度（- 导航栏），row-height=50 → 行数
const ROW_HEIGHT = 50;
const viewportRows = ref(Math.max(8, Math.floor((window.innerHeight - 80) / ROW_HEIGHT)));
function updateViewportRows() {
  viewportRows.value = Math.max(8, Math.floor((window.innerHeight - 80) / ROW_HEIGHT));
}
onMounted(() => {
  window.addEventListener('resize', updateViewportRows);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportRows);
});

const gridLayoutData = computed((): GridItemData[] => {
  // 一卡片一屏：固定顺序（左列卡片 → 右列图表卡片），
  // 每张卡占满整行（w=12），y = 序号 × 视口高度（避免重叠）
  const order = [
    DashboardLayout.botComparison,
    DashboardLayout.allOpenTrades,
    DashboardLayout.allClosedTrades,
    DashboardLayout.tradesLogChart,
    DashboardLayout.dailyChart,
    DashboardLayout.cumChartChart,
    DashboardLayout.walletHistoryChart,
    DashboardLayout.profitDistributionChart,
  ];
  return order.map((i, idx) => ({
    i,
    x: 0,
    y: idx * viewportRows.value,
    w: 12,
    h: viewportRows.value,
  }));
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

const gridLayoutCumChart = computed((): GridItemData => {
  return findGridLayout(gridLayoutData.value, DashboardLayout.cumChartChart);
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
    sm: layoutStore.getDashboardLayoutSm,
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
    style="padding: 1px"
    :row-height="50"
    :layout="gridLayoutData"
    :vertical-compact="false"
    :margin="[20, 20]"
    :responsive-layouts="responsiveGridLayouts"
    :is-resizable="!isLayoutLocked"
    :is-draggable="!isLayoutLocked"
    :responsive="true"
    :prevent-collision="true"
    :cols="{ lg: 12, md: 12, sm: 12, xs: 4, xxs: 2 }"
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
        <DraggableContainer :header="`Profit over time ${botStore.botCount > 1 ? 'combined' : ''}`">
          <PeriodBreakdown multi-bot-view />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutBotComparison.i"
        :x="gridLayoutBotComparison.x"
        :y="gridLayoutBotComparison.y"
        :w="gridLayoutBotComparison.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Bot comparison">
          <BotComparisonList />
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
          header="Open Trades"
          info-text="Open trades of all selected bots. Click on a trade to go to the trade page for that trade/bot."
        >
          <TradeList active-trades :trades="botStore.allOpenTradesSelectedBots" multi-bot-view />
        </DraggableContainer>
      </GridItem>
      <GridItem
        v-bind="gridItemProps"
        :i="gridLayoutCumChart.i"
        :x="gridLayoutCumChart.x"
        :y="gridLayoutCumChart.y"
        :w="gridLayoutCumChart.w"
        :h="viewportRows"
        :min-w="3"
        :min-h="4"
        drag-allow-from=".drag-header"
      >
        <DraggableContainer header="Cumulative Profit">
          <CumProfitChart
            :trades="botStore.allTradesSelectedBots"
            :open-trades="botStore.allOpenTradesSelectedBots"
            :show-title="false"
          />
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
        <DraggableContainer header="Wallet History">
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
          header="Closed Trades"
          info-text="Closed trades for all selected bots. Click on a trade to go to the trade page for that trade/bot."
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
        <DraggableContainer header="Profit Distribution">
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
        <DraggableContainer header="Trades Log">
          <TradesLogChart :trades="botStore.allTradesSelectedBots" :show-title="false" />
        </DraggableContainer>
      </GridItem>
    </template>
  </GridLayout>
</template>
