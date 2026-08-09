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

// 一卡片一屏：卡片高度 = 视口高度（- 导航栏）
// 关键：vue-grid-layout 每行实际占用 = ROW_HEIGHT + MARGIN = 70px
const ROW_HEIGHT = 50;
const NAV_HEIGHT = 120; // 顶部导航 + 页头高度
const MARGIN = 20;     // 卡片间距
const ROW_STEP = ROW_HEIGHT + MARGIN; // 每行实际占 70px
// 可用视口高度对应的行数（每行 70px），保证大卡片底部在屏幕内
const viewportRows = ref(
  Math.max(6, Math.floor((window.innerHeight - NAV_HEIGHT) / ROW_STEP)),
);
// Bot Comparison 矮卡（约 3 行 = 190px）；Cumulative Profit 紧接其后（间距即 margin）
const botComparisonRows = computed(() => 3);
const cumProfitRows = computed(() => {
  const botPx = botComparisonRows.value * ROW_STEP; // 矮卡占的像素（含其行间距）
  const available = window.innerHeight - NAV_HEIGHT - botPx;
  return Math.max(3, Math.floor(available / ROW_STEP));
});
function updateViewportRows() {
  viewportRows.value = Math.max(
    6,
    Math.floor((window.innerHeight - NAV_HEIGHT) / ROW_STEP),
  );
}
onMounted(() => {
  window.addEventListener('resize', updateViewportRows);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportRows);
});

const gridLayoutData = computed((): GridItemData[] => {
  // 布局规则：
  // 首屏两张卡上下排列：
  //   Bot Comparison 上（内容少，矮卡 ~3行）
  //   Cumulative Profit 下（利润曲线，占满剩余空间完整显示）
  // 其余每张卡一屏（w=12，高度 = 视口高度）
  const order: { i: number; w: number }[] = [
    { i: DashboardLayout.botComparison, w: 12 },
    { i: DashboardLayout.cumChartChart, w: 12 },
    { i: DashboardLayout.allOpenTrades, w: 12 },
    { i: DashboardLayout.allClosedTrades, w: 12 },
    { i: DashboardLayout.tradesLogChart, w: 12 },
    { i: DashboardLayout.dailyChart, w: 12 },
    { i: DashboardLayout.walletHistoryChart, w: 12 },
    { i: DashboardLayout.profitDistributionChart, w: 12 },
  ];
  // 首屏两卡：Bot Comparison 矮卡 + Cumulative Profit 占剩余空间（精确计算）
  const botRows = botComparisonRows.value;
  const cumRows = cumProfitRows.value;
  return order.map((item, idx) => {
    if (idx === 0) {
      // 首屏上卡：矮卡
      return { i: item.i, x: 0, y: 0, w: item.w, h: botRows };
    }
    if (idx === 1) {
      // 首屏下卡：紧接矮卡下方（y=botRows，间距即 margin 20px）
      return { i: item.i, x: 0, y: botRows, w: item.w, h: cumRows };
    }
    // 后续卡片：每张一屏
    return {
      i: item.i,
      x: 0,
      y: viewportRows.value + (idx - 2) * viewportRows.value,
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
        :h="botComparisonRows"
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
        :h="cumProfitRows"
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
