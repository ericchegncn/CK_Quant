<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const botStore = useBotStore();
const { t } = useI18n();

const activeBot = computed(() => botStore.activeBot);
const profit = computed(() => activeBot.value?.profit);
const stakeCurrency = computed(() => activeBot.value?.stakeCurrency || 'USDT');
const stakeDecimals = computed(() => activeBot.value?.stakeCurrencyDecimals ?? 3);

function stakeValue(value?: number | null): string {
  return value === undefined || value === null
    ? 'N/A'
    : formatPriceCurrency(value, stakeCurrency.value, stakeDecimals.value);
}

function fiatValue(value?: number | null): string {
  return value === undefined || value === null ? 'N/A' : formatPriceCurrency(value, 'USD', 3);
}

function timestampWithAge(humanized?: string, timestamp?: number): string {
  if (!timestamp) return 'N/A';
  const date = timestampms(timestamp);
  return humanized ? `${humanized} (${date})` : date;
}

const roiItems = computed(() => {
  if (!profit.value) return [];
  return [
    {
      label: t('workspace.roiClosedTrades'),
      value: `${stakeValue(profit.value.profit_closed_coin)} (${formatPercent(
        profit.value.profit_closed_ratio,
        2,
      )})`,
      sum: `Σ ${formatPercent(profit.value.profit_closed_ratio_sum, 2)}`,
      fiat: fiatValue(profit.value.profit_closed_fiat),
      positive: profit.value.profit_closed_coin >= 0,
    },
    {
      label: t('workspace.roiAllTrades'),
      value: `${stakeValue(profit.value.profit_all_coin)} (${formatPercent(
        profit.value.profit_all_ratio,
        2,
      )})`,
      sum: `Σ ${formatPercent(profit.value.profit_all_ratio_sum, 2)}`,
      fiat: fiatValue(profit.value.profit_all_fiat),
      positive: profit.value.profit_all_coin >= 0,
    },
  ];
});

const metricItems = computed(() => {
  if (!profit.value) return [];
  const stats = profit.value;
  return [
    { label: t('workspace.totalTradeCount'), value: `${stats.trade_count ?? 0}` },
    { label: t('workspace.botStarted'), value: timestampWithAge('', stats.bot_start_timestamp) },
    {
      label: t('workspace.firstTradeOpened'),
      value: timestampWithAge(stats.first_trade_humanized, stats.first_trade_timestamp),
    },
    {
      label: t('workspace.lastTradeOpened'),
      value: timestampWithAge(stats.latest_trade_humanized, stats.latest_trade_timestamp),
    },
    {
      label: t('workspace.winLoss'),
      value: `${stats.winning_trades ?? 0} / ${stats.losing_trades ?? 0}`,
      accent: 'split',
    },
    {
      label: t('workspace.winRate'),
      value: formatPercent(stats.winrate ?? 0, 2),
      accent: (stats.winrate ?? 0) >= 0.5 ? 'profit' : 'loss',
    },
    {
      label: t('workspace.expectancy'),
      value: `${formatNumber(stats.expectancy, 2)} (${formatNumber(stats.expectancy_ratio, 2)})`,
    },
    { label: t('workspace.averageDuration'), value: stats.avg_duration || 'N/A' },
    {
      label: t('workspace.bestPerforming'),
      value: stats.best_pair
        ? `${stats.best_pair}: ${stakeValue(stats.best_pair_profit_abs)} (${formatPercent(
            stats.best_pair_profit_ratio,
            2,
          )})`
        : 'N/A',
      accent: 'profit',
    },
    { label: t('workspace.tradingVolume'), value: stakeValue(stats.trading_volume) },
    { label: t('workspace.profitFactor'), value: formatNumber(stats.profit_factor, 2) },
    {
      label: t('workspace.maxDrawdown'),
      value: `${formatPercent(stats.max_drawdown ?? 0, 2)} (${stakeValue(stats.max_drawdown_abs)})`,
      detail:
        stats.max_drawdown_start_timestamp && stats.max_drawdown_end_timestamp
          ? `${t('workspace.fromTo', {
              from: `${timestampms(stats.max_drawdown_start_timestamp)} (${stakeValue(stats.drawdown_high)})`,
              to: `${timestampms(stats.max_drawdown_end_timestamp)} (${stakeValue(stats.drawdown_low)})`,
            })}`
          : '',
      accent: 'loss',
    },
    {
      label: t('workspace.currentDrawdown'),
      value: `${formatPercent(stats.current_drawdown ?? 0, 2)} (${stakeValue(
        stats.current_drawdown_abs,
      )})`,
      detail: stats.current_drawdown_start_timestamp
        ? t('workspace.since', {
            date: `${timestampms(stats.current_drawdown_start_timestamp)} (${stakeValue(
              stats.current_drawdown_high,
            )})`,
          })
        : '',
      accent: 'loss',
    },
  ];
});
</script>

<template>
  <div
    class="dashboard-overview grid min-h-full grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1.04fr)_minmax(420px,0.96fr)] lg:items-start"
  >
    <div class="flex min-w-0 flex-col gap-4">
      <section class="overflow-hidden rounded-xl border border-default/60 bg-default/30">
        <BotComparisonList />
      </section>

      <section v-if="profit" class="space-y-3">
        <div class="grid gap-3 md:grid-cols-2">
          <article
            v-for="item in roiItems"
            :key="item.label"
            class="relative overflow-hidden rounded-xl border border-default/60 bg-elevated/55 p-4"
          >
            <div
              class="absolute inset-y-0 left-0 w-1"
              :class="item.positive ? 'bg-emerald-500' : 'bg-rose-500'"
            />
            <p class="text-xs font-medium uppercase tracking-wide text-muted">{{ item.label }}</p>
            <div class="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <strong
                class="text-lg tabular-nums"
                :class="item.positive ? 'text-profit' : 'text-loss'"
                >{{ item.value }}</strong
              >
              <span class="text-xs tabular-nums text-muted">{{ item.sum }}</span>
            </div>
            <p class="mt-1 text-sm tabular-nums text-muted">{{ item.fiat }}</p>
          </article>
        </div>

        <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <article
            v-for="item in metricItems"
            :key="item.label"
            class="min-w-0 rounded-lg border border-default/50 bg-default/25 px-3.5 py-3"
          >
            <p class="text-sm font-medium text-muted">{{ item.label }}</p>
            <p
              class="mt-1.5 break-words text-base font-semibold leading-snug tabular-nums"
              :class="{
                'text-profit': item.accent === 'profit',
                'text-loss': item.accent === 'loss',
              }"
            >
              {{ item.value }}
            </p>
            <p v-if="item.detail" class="mt-1.5 break-words text-sm leading-relaxed text-muted">
              {{ item.detail }}
            </p>
          </article>
        </div>
      </section>
    </div>

    <section
      class="profit-curve h-[360px] min-h-[360px] rounded-xl border border-default/60 bg-default/20 p-2 lg:sticky lg:top-4 lg:h-[620px] lg:min-h-[620px]"
    >
      <div class="flex items-center justify-between px-2 pt-1">
        <h3 class="text-sm font-semibold">{{ t('workspace.cumulativeProfit') }}</h3>
        <span class="text-xs text-muted">{{ activeBot?.uiBotName || activeBot?.botName }}</span>
      </div>
      <div class="h-[320px] min-h-[320px] lg:h-[580px] lg:min-h-[580px]">
        <CumProfitChart
          :trades="botStore.allTradesSelectedBots"
          :open-trades="botStore.allOpenTradesSelectedBots"
          :show-title="false"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-overview {
  background:
    radial-gradient(circle at 12% 0%, rgb(16 185 129 / 8%), transparent 34%),
    radial-gradient(circle at 88% 32%, rgb(59 130 246 / 8%), transparent 36%);
}
</style>
