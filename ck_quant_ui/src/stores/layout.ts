import type { GridItemData } from '@/types';

export enum TradeLayout {
  multiPane = 0,
  openTrades = 1,
  tradeHistory = 2,
  tradeDetail = 3,
  chartView = 4,
}

export enum DashboardLayout {
  dailyChart = 0,
  botComparison = 1,
  allOpenTrades = 2,
  cumChartChart = 3,
  allClosedTrades = 4,
  profitDistributionChart = 5,
  tradesLogChart = 6,
  walletHistoryChart = 7,
}

// Define default layouts
const DEFAULT_TRADING_LAYOUT: GridItemData[] = [
  { i: TradeLayout.multiPane, x: 0, y: 0, w: 12, h: 10 },
  { i: TradeLayout.chartView, x: 0, y: 10, w: 12, h: 14 },
  { i: TradeLayout.openTrades, x: 0, y: 24, w: 12, h: 14 },
  { i: TradeLayout.tradeHistory, x: 0, y: 38, w: 12, h: 14 },
  { i: TradeLayout.tradeDetail, x: 0, y: 52, w: 12, h: 6 },
];

// Mobile layout: keep the main trading cards visible in a single scrollable column.
const DEFAULT_TRADING_LAYOUT_SM: GridItemData[] = [
  { i: TradeLayout.multiPane, x: 0, y: 0, w: 12, h: 10 },
  { i: TradeLayout.chartView, x: 0, y: 10, w: 12, h: 12 },
  { i: TradeLayout.openTrades, x: 0, y: 22, w: 12, h: 12 },
  { i: TradeLayout.tradeHistory, x: 0, y: 34, w: 12, h: 12 },
  { i: TradeLayout.tradeDetail, x: 0, y: 46, w: 12, h: 6 },
];

function isLegacyTradingLayout(layout: GridItemData[]): boolean {
  const multiPane = layout.find((item) => item.i === TradeLayout.multiPane);
  const openTrades = layout.find((item) => item.i === TradeLayout.openTrades);
  const tradeHistory = layout.find((item) => item.i === TradeLayout.tradeHistory);
  const tradeDetail = layout.find((item) => item.i === TradeLayout.tradeDetail);

  return (
    multiPane?.h === 35 &&
    openTrades?.y === 14 &&
    openTrades.h === 5 &&
    tradeDetail?.y === 19 &&
    tradeDetail.h === 6 &&
    tradeHistory?.y === 25 &&
    tradeHistory.h === 10
  );
}

const DEFAULT_DASHBOARD_LAYOUT: GridItemData[] = [
  { i: DashboardLayout.botComparison, x: 0, y: 0, w: 12, h: 10 },
  { i: DashboardLayout.allOpenTrades, x: 0, y: 10, w: 12, h: 6 },
  { i: DashboardLayout.allClosedTrades, x: 0, y: 16, w: 12, h: 6 },
  { i: DashboardLayout.tradesLogChart, x: 0, y: 22, w: 12, h: 6 },
  { i: DashboardLayout.dailyChart, x: 0, y: 28, w: 12, h: 6 },
  { i: DashboardLayout.walletHistoryChart, x: 0, y: 34, w: 12, h: 6 },
  { i: DashboardLayout.profitDistributionChart, x: 0, y: 40, w: 12, h: 6 },
];

const DEFAULT_DASHBOARD_LAYOUT_SM: GridItemData[] = [
  { i: DashboardLayout.botComparison, x: 0, y: 0, w: 12, h: 22 },
  { i: DashboardLayout.allOpenTrades, x: 0, y: 22, w: 12, h: 8 },
  { i: DashboardLayout.dailyChart, x: 0, y: 30, w: 12, h: 6 },
  { i: DashboardLayout.walletHistoryChart, x: 0, y: 36, w: 12, h: 6 },
  { i: DashboardLayout.profitDistributionChart, x: 0, y: 42, w: 12, h: 6 },
  { i: DashboardLayout.tradesLogChart, x: 0, y: 48, w: 12, h: 6 },
  { i: DashboardLayout.allClosedTrades, x: 0, y: 54, w: 12, h: 8 },
];

const STORE_LAYOUTS = 'ftLayoutSettings_v3';


function migrateLayoutSettings() {
  const STORE_DASHBOARD_LAYOUT = 'ftDashboardLayout';
  const STORE_TRADING_LAYOUT = 'ftTradingLayout';
  const STORE_LAYOUT_LOCK = 'ftLayoutLocked';
  const STORE_LAYOUTS_V1 = 'ftLayoutSettings';

  // If new does not exist
  if (localStorage.getItem(STORE_DASHBOARD_LAYOUT) !== null) {
    console.log('Migrating dashboard settings');
    const layoutLocked = localStorage.getItem(STORE_LAYOUT_LOCK);
    const tradingLayout = localStorage.getItem(STORE_TRADING_LAYOUT);
    const dashboardLayout = localStorage.getItem(STORE_DASHBOARD_LAYOUT);

    const res = {
      dashboardLayout,
      tradingLayout,
      layoutLocked,
    };
    localStorage.setItem(STORE_LAYOUTS, JSON.stringify(res));
  }
  localStorage.removeItem(STORE_LAYOUT_LOCK);
  localStorage.removeItem(STORE_TRADING_LAYOUT);
  localStorage.removeItem(STORE_DASHBOARD_LAYOUT);
// Remove v1/v2 layout cache so the new default layout loads
  localStorage.removeItem(STORE_LAYOUTS_V1);
  localStorage.removeItem('ftLayoutSettings_v2');

}
migrateLayoutSettings();
/**
 * Helper function finding a layout entry
 * @param gridLayout Array of grid layouts used in this layout. Must be passed to GridLayout, too.
 * @param name Name within the dashboard layout to find
 */
export function findGridLayout(gridLayout: GridItemData[], name: number): GridItemData {
  let layout = gridLayout.find((value) => value.i === name);
  if (!layout) {
    layout = { i: name, x: 0, y: 0, w: 4, h: 6 };
  }
  return layout;
}

export const useLayoutStore = defineStore(
  'layoutStore',
  () => {
    const dashboardLayout = ref<GridItemData[]>(deepClone(DEFAULT_DASHBOARD_LAYOUT));
    const tradingLayout = ref<GridItemData[]>(deepClone(DEFAULT_TRADING_LAYOUT));
    const layoutLocked = ref(true);

    const getDashboardLayoutSm = computed(() => [...DEFAULT_DASHBOARD_LAYOUT_SM]);
    const getTradingLayoutSm = computed(() => [...DEFAULT_TRADING_LAYOUT_SM]);

    function resetTradingLayout() {
      tradingLayout.value = deepClone(DEFAULT_TRADING_LAYOUT);
    }

    function resetDashboardLayout() {
      dashboardLayout.value = deepClone(DEFAULT_DASHBOARD_LAYOUT);
    }

    return {
      dashboardLayout,
      tradingLayout,
      layoutLocked,
      getDashboardLayoutSm,
      getTradingLayoutSm,
      resetTradingLayout,
      resetDashboardLayout,
    };
  },
  {
    persist: {
      key: STORE_LAYOUTS,
      afterHydrate: (context) => {
        if (
          context.store.dashboardLayout === null ||
          typeof context.store.dashboardLayout === 'string' ||
          context.store.dashboardLayout.length === 0 ||
          typeof context.store.dashboardLayout[0]['i'] === 'string' ||
          context.store.dashboardLayout.length < DEFAULT_DASHBOARD_LAYOUT.length
        ) {
          console.log('loading dashboard Layout from default.');
          context.store.dashboardLayout = deepClone(DEFAULT_DASHBOARD_LAYOUT);
        }
        if (
          context.store.tradingLayout === null ||
          typeof context.store.tradingLayout === 'string' ||
          context.store.tradingLayout.length === 0 ||
          typeof context.store.tradingLayout[0]['i'] === 'string' ||
          context.store.tradingLayout.length < DEFAULT_TRADING_LAYOUT.length
        ) {
          console.log('loading trading Layout from default.');
          context.store.tradingLayout = deepClone(DEFAULT_TRADING_LAYOUT);
        } else if (isLegacyTradingLayout(context.store.tradingLayout)) {
          console.log('upgrading trading layout card heights and spacing.');
          context.store.tradingLayout = deepClone(DEFAULT_TRADING_LAYOUT);
        }
      },
    },
  },
);
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useLayoutStore, import.meta.hot));
}
