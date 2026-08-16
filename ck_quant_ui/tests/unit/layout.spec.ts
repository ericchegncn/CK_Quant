import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { DashboardLayout, TradeLayout, useLayoutStore } from '@/stores/layout';

describe('mobile trading layout', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('keeps the summary, chart, open trades, and closed trades visible', () => {
    const layout = useLayoutStore().getTradingLayoutSm;
    const visibleCards = [
      TradeLayout.multiPane,
      TradeLayout.chartView,
      TradeLayout.openTrades,
      TradeLayout.tradeHistory,
    ];

    for (const card of visibleCards) {
      expect(layout.find((item) => item.i === card)?.h).toBeGreaterThan(0);
    }
  });

  it('stacks mobile trading cards without overlap', () => {
    const layout = [...useLayoutStore().getTradingLayoutSm].sort((a, b) => a.y - b.y);

    for (let index = 1; index < layout.length; index += 1) {
      const previous = layout[index - 1]!;
      const current = layout[index]!;
      expect(current.y).toBeGreaterThanOrEqual(previous.y + previous.h);
    }
  });

  it('uses equal heights for open and closed trades', () => {
    const layout = useLayoutStore().getTradingLayoutSm;
    const openTrades = layout.find((item) => item.i === TradeLayout.openTrades)!;
    const closedTrades = layout.find((item) => item.i === TradeLayout.tradeHistory)!;

    expect(openTrades.h).toBe(closedTrades.h);
    expect(closedTrades.y).toBe(openTrades.y + openTrades.h);
  });
});

describe('desktop trading layout', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('places equal-height open and closed trade cards next to each other', () => {
    const layout = useLayoutStore().tradingLayout;
    const openTrades = layout.find((item) => item.i === TradeLayout.openTrades)!;
    const closedTrades = layout.find((item) => item.i === TradeLayout.tradeHistory)!;
    const chartView = layout.find((item) => item.i === TradeLayout.chartView)!;

    // 未平仓/已平仓卡片高度与图表卡一致（用户要求）
    expect(openTrades.h).toBe(chartView.h);
    expect(closedTrades.h).toBe(openTrades.h);
    expect(closedTrades.y).toBe(openTrades.y + openTrades.h);
  });
});

describe('dashboard overview layout', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('uses one merged overview card instead of a separate cumulative-profit card', () => {
    const layout = useLayoutStore().getDashboardLayoutSm;

    expect(layout[0]?.i).toBe(DashboardLayout.botComparison);
    expect(layout[0]?.h).toBeGreaterThanOrEqual(22);
    expect(layout.some((item) => item.i === DashboardLayout.cumChartChart)).toBe(false);
  });

  it('stacks the merged overview and remaining dashboard cards without overlap', () => {
    const layout = [...useLayoutStore().getDashboardLayoutSm].sort((a, b) => a.y - b.y);

    for (let index = 1; index < layout.length; index += 1) {
      expect(layout[index]!.y).toBeGreaterThanOrEqual(layout[index - 1]!.y + layout[index - 1]!.h);
    }
  });
});
