<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import axios from 'axios';

import type { ClosedTrade, CumProfitChartData, Trade } from '@/types';
import type { TableColumn } from '@nuxt/ui';

const { t } = useI18n();

definePage({
  meta: {
    allowAnonymous: true,
  },
});

const POLL_INTERVAL_MS = 60_000;
const OVERVIEW_ENDPOINT = '/api/v1/public/overview';
// Stake amounts render with 3 decimals, exactly like the dashboard's overview.
const STAKE_DECIMALS = 3;
// Anything the payload does not carry shows as an em dash - never "N/A".
const MISSING = '—';
// Below this magnitude a profit curve is unambiguously a *ratio* curve
// (0.1131 == +11.31%) rather than an absolute one.
const RATIO_HISTORY_CEILING = 1;

/**
 * Public overview payload (contract v2). Every ratio is a ratio
 * (`0.1131` == `11.31%`) and every amount is denominated in `stake_currency`.
 * All fields stay optional so a partially implemented or older bot renders
 * gracefully instead of crashing.
 */
interface PublicProfitPoint {
  date: number;
  profit?: number;
  profit_abs?: number;
}

interface PublicOverviewPayload {
  label?: string;
  bot_state?: string;
  runmode?: string;
  version?: string;
  exchange?: string;
  trading_mode?: string;
  start_date?: string;
  uptime_seconds?: number;
  as_of?: string;
  open_trades?: number;
  max_open_trades?: number;
  trade_count?: number;
  win_count?: number;
  loss_count?: number;
  win_rate?: number;
  profit_factor?: number;
  expectancy?: number;
  expectancy_ratio?: number;
  avg_duration_seconds?: number;
  trading_volume?: number;
  profit_total_abs?: number;
  profit_total_ratio?: number;
  profit_closed_abs?: number;
  profit_closed_ratio?: number;
  profit_open_abs?: number;
  profit_open_ratio?: number;
  profit_total_ratio_sum?: number;
  profit_closed_ratio_sum?: number;
  starting_capital?: number;
  balance_total?: number;
  stake_currency?: string;
  max_drawdown_ratio?: number;
  max_drawdown_abs?: number;
  current_drawdown_ratio?: number;
  current_drawdown_abs?: number;
  open_profit_abs?: number;
  profit_history?: PublicProfitPoint[];
  // Tolerated extras: a bot may publish fiat conversions or trade timestamps on
  // top of the contract. Shown when present, ignored otherwise.
  first_trade_timestamp?: number;
  last_trade_timestamp?: number;
  profit_total_fiat?: number;
  profit_closed_fiat?: number;
  profit?: PublicOverviewPayload;
  summary?: PublicOverviewPayload;
}

type ShowcaseState = 'loading' | 'ready' | 'disabled' | 'error';

/** One showcase block: a single bot reached through its own API base URL. */
interface ShowcaseBlock {
  key: string;
  endpoint: string;
  state: ShowcaseState;
  payload: PublicOverviewPayload | null;
  updatedAt: number | null;
}

/**
 * `?api=<url>` may be repeated to showcase several bots from one page. The
 * parameters are rendered in order; with no `?api=` the page falls back to the
 * same origin (a single bot serving its own frontend).
 */
function buildBlocks(): ShowcaseBlock[] {
  const params = new URLSearchParams(window.location.search).getAll('api');
  const requested = params.length > 0 ? params : [window.location.origin];
  const seen = new Set<string>();
  const result: ShowcaseBlock[] = [];
  for (const entry of requested) {
    const value = entry.trim().replace(/\/+$/, '');
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push({
      key: value,
      endpoint: `${value}${OVERVIEW_ENDPOINT}`,
      state: 'loading',
      payload: null,
      updatedAt: null,
    });
  }
  if (result.length === 0) {
    const origin = window.location.origin;
    result.push({
      key: origin,
      endpoint: `${origin}${OVERVIEW_ENDPOINT}`,
      state: 'loading',
      payload: null,
      updatedAt: null,
    });
  }
  return result;
}

const blocks = ref<ShowcaseBlock[]>(buildBlocks());

// A dedicated, unauthenticated client. The shared client in composables/api.ts
// attaches a bearer token and retries on 401, which is exactly what a guest
// cannot (and must not) do.
const http = axios.create({ timeout: 15000 });

/**
 * Field names an older deployment may still publish. Reading them keeps a
 * shared link working unchanged while a bot is upgraded, instead of degrading
 * to an em dash for a value the server actually sent.
 */
const FIELD_ALIASES: Record<string, string[]> = {
  bot_state: ['status', 'state'],
  open_trades: ['open_trade_count'],
  win_rate: ['winrate'],
  max_drawdown_ratio: ['max_drawdown'],
  profit_total_ratio: ['profit_all_ratio'],
  profit_total_abs: ['profit_abs', 'profit_all_coin'],
  profit_closed_abs: ['profit_closed_coin'],
  start_date: ['bot_start_date'],
};

function readPoint(source: PublicOverviewPayload, key: string): unknown {
  const candidates = [key, ...(FIELD_ALIASES[key] ?? [])];
  for (const candidate of candidates) {
    const value = (source as Record<string, unknown>)[candidate];
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

/** Read a field off the payload, tolerating a `profit` / `summary` wrapper. */
function rawField(block: ShowcaseBlock, key: keyof PublicOverviewPayload): unknown {
  const source = block.payload;
  if (!source) return undefined;
  const direct = readPoint(source, key as string);
  if (direct !== undefined) return direct;
  for (const nested of [source.profit, source.summary]) {
    if (!nested) continue;
    const value = readPoint(nested, key as string);
    if (value !== undefined) return value;
  }
  return undefined;
}

function fieldNumber(block: ShowcaseBlock, key: keyof PublicOverviewPayload): number | undefined {
  const value = rawField(block, key);
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

async function loadBlock(block: ShowcaseBlock): Promise<void> {
  try {
    const { data } = await http.get<PublicOverviewPayload>(block.endpoint);
    block.payload = data ?? null;
    block.updatedAt = Date.now();
    block.state = 'ready';
  } catch (err) {
    // Keep the last good snapshot on screen; only surface a message when there
    // is nothing to show for this block yet. One failing block never affects
    // the others.
    if (block.payload) return;
    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
    block.state = status === 404 ? 'disabled' : 'error';
  }
}

function retryBlock(block: ShowcaseBlock) {
  block.state = 'loading';
  void loadBlock(block);
}

let pollTimer: number | undefined;

onMounted(() => {
  blocks.value.forEach((block) => void loadBlock(block));
  pollTimer = window.setInterval(() => {
    blocks.value.forEach((block) => void loadBlock(block));
  }, POLL_INTERVAL_MS);
});

onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer);
});

// Stable empty collection: an inline literal would be re-created on every
// render and make the chart recompute for no reason. Typed exactly like the
// chart's `trades` prop - the public page has no per-trade rows at all and
// feeds the curve through `profit-history`.
const NO_TRADES: ClosedTrade[] = [];

// --- formatting helpers -----------------------------------------------------
// The shared formatters answer "N/A" (or "N/A%") for a missing value, which the
// showcase must never show. Each helper therefore checks for a real number
// first and only then delegates.
function moneyText(value: number | undefined, currency: string, decimals = STAKE_DECIMALS) {
  return value === undefined ? MISSING : formatPriceCurrency(value, currency, decimals);
}

function percentText(value: number | undefined, decimals = 2) {
  return value === undefined ? MISSING : formatPercent(value, decimals);
}

function numberText(value: number | undefined, decimals = 0) {
  return value === undefined ? MISSING : formatNumber(value, decimals);
}

function countText(value: number | undefined) {
  return value === undefined ? MISSING : formatNumber(value, 0);
}

function timestampText(value: number | undefined) {
  return value === undefined ? MISSING : timestampms(value);
}

function stakeCurrency(block: ShowcaseBlock): string {
  const value = rawField(block, 'stake_currency');
  return typeof value === 'string' && value ? value : 'USDT';
}

// --- view models ------------------------------------------------------------
type Accent = 'profit' | 'loss';

interface OverviewRow {
  label: string;
  status: string;
  statusClass: string;
  trades: string;
  profitOpen?: number;
  profitOpenRatio?: number;
  profitClosed?: number;
  profitClosedRatio?: number;
  balance?: number;
  balanceCurrency: string;
  winCount?: number;
  lossCount?: number;
  runmode?: string;
}

interface RoiCard {
  label: string;
  value: string;
  sum: string;
  fiat: string;
  positive: boolean;
}

interface MetricItem {
  label: string;
  value: string;
  accent?: Accent;
}

interface BlockView {
  block: ShowcaseBlock;
  title: string;
  row: OverviewRow;
  roi: RoiCard[];
  metrics: MetricItem[];
  history: CumProfitChartData[];
  chartOpenTrades: Trade[];
  updatedText: string;
}

function blockTitle(block: ShowcaseBlock): string {
  const label = rawField(block, 'label');
  return typeof label === 'string' && label ? label : t('showcase.defaultLabel');
}

function blockStatus(block: ShowcaseBlock): { text: string; className: string } {
  const raw = rawField(block, 'bot_state');
  const normalized = typeof raw === 'string' ? raw.toLowerCase() : '';
  if (normalized === 'running' || normalized.includes('run')) {
    return { text: t('showcase.running'), className: 'showcase-status-pill--running' };
  }
  if (normalized === 'stopped' || normalized.includes('stop')) {
    return { text: t('showcase.stopped'), className: 'showcase-status-pill--stopped' };
  }
  return { text: t('showcase.unknown'), className: 'showcase-status-pill--unknown' };
}

function blockRunmode(block: ShowcaseBlock): string | undefined {
  const raw = rawField(block, 'runmode');
  const runmode = typeof raw === 'string' ? raw.toLowerCase() : '';
  if (runmode.includes('dry')) return t('workspace.dry');
  if (runmode.includes('live')) return t('workspace.live');
  return undefined;
}

function overviewRow(block: ShowcaseBlock): OverviewRow {
  const status = blockStatus(block);
  const openTrades = fieldNumber(block, 'open_trades');
  const maxOpenTrades = fieldNumber(block, 'max_open_trades');
  return {
    label: blockTitle(block),
    status: status.text,
    statusClass: status.className,
    trades:
      openTrades === undefined && maxOpenTrades === undefined
        ? MISSING
        : `${countText(openTrades)} / ${countText(maxOpenTrades)}`,
    profitOpen: fieldNumber(block, 'profit_open_abs') ?? fieldNumber(block, 'open_profit_abs'),
    profitOpenRatio: fieldNumber(block, 'profit_open_ratio'),
    profitClosed: fieldNumber(block, 'profit_closed_abs'),
    profitClosedRatio: fieldNumber(block, 'profit_closed_ratio'),
    balance: fieldNumber(block, 'balance_total'),
    balanceCurrency: stakeCurrency(block),
    winCount: fieldNumber(block, 'win_count'),
    lossCount: fieldNumber(block, 'loss_count'),
    runmode: blockRunmode(block),
  };
}

function roiCards(block: ShowcaseBlock): RoiCard[] {
  const currency = stakeCurrency(block);
  const build = (
    label: string,
    abs: number | undefined,
    ratio: number | undefined,
    sum: number | undefined,
    fiat: number | undefined,
  ): RoiCard => ({
    label,
    value:
      abs === undefined && ratio === undefined
        ? MISSING
        : `${moneyText(abs, currency)} (${percentText(ratio)})`,
    sum: `Σ ${percentText(sum)}`,
    fiat: fiat === undefined ? MISSING : formatPriceCurrency(fiat, 'USD', STAKE_DECIMALS),
    positive: (abs ?? ratio ?? 0) >= 0,
  });
  return [
    build(
      t('showcase.roiAllTrades'),
      fieldNumber(block, 'profit_total_abs'),
      fieldNumber(block, 'profit_total_ratio'),
      fieldNumber(block, 'profit_total_ratio_sum'),
      fieldNumber(block, 'profit_total_fiat'),
    ),
    build(
      t('showcase.roiClosedTrades'),
      fieldNumber(block, 'profit_closed_abs'),
      fieldNumber(block, 'profit_closed_ratio'),
      fieldNumber(block, 'profit_closed_ratio_sum'),
      fieldNumber(block, 'profit_closed_fiat'),
    ),
  ];
}

function drawdownText(ratio: number | undefined, abs: number | undefined, currency: string) {
  const percent = percentText(ratio);
  return abs === undefined ? percent : `${percent} (${moneyText(abs, currency)})`;
}

function durationText(seconds: number | undefined) {
  return seconds === undefined || seconds <= 0 ? MISSING : humanizeDurationFromSeconds(seconds);
}

function startedText(block: ShowcaseBlock): string {
  const startDate = rawField(block, 'start_date');
  if (typeof startDate === 'string' && startDate) {
    const parsed = Date.parse(startDate);
    if (!Number.isNaN(parsed)) return timestampText(parsed);
  }
  // Fall back to "now minus uptime" when only the runtime is published.
  const uptime = fieldNumber(block, 'uptime_seconds');
  return uptime === undefined ? MISSING : timestampText(Date.now() - uptime * 1000);
}

function metricItems(block: ShowcaseBlock): MetricItem[] {
  const currency = stakeCurrency(block);
  const winRate = fieldNumber(block, 'win_rate');
  const expectancy = fieldNumber(block, 'expectancy');
  const expectancyRatio = fieldNumber(block, 'expectancy_ratio');
  return [
    { label: t('showcase.metricTradeCount'), value: countText(fieldNumber(block, 'trade_count')) },
    { label: t('showcase.metricBotStarted'), value: startedText(block) },
    {
      label: t('showcase.metricFirstTrade'),
      value: timestampText(fieldNumber(block, 'first_trade_timestamp')),
    },
    {
      label: t('showcase.metricLastTrade'),
      value: timestampText(fieldNumber(block, 'last_trade_timestamp')),
    },
    {
      label: t('showcase.metricWinLoss'),
      value: `${countText(fieldNumber(block, 'win_count'))} / ${countText(
        fieldNumber(block, 'loss_count'),
      )}`,
    },
    {
      label: t('showcase.winRate'),
      value: percentText(winRate),
      accent: winRate === undefined ? undefined : winRate >= 0.5 ? 'profit' : 'loss',
    },
    {
      label: t('showcase.expectancy'),
      value:
        expectancy === undefined && expectancyRatio === undefined
          ? MISSING
          : `${numberText(expectancy, 2)} (${numberText(expectancyRatio, 2)})`,
    },
    {
      label: t('showcase.metricAvgDuration'),
      value: durationText(fieldNumber(block, 'avg_duration_seconds')),
    },
    {
      label: t('showcase.metricTradingVolume'),
      value: moneyText(fieldNumber(block, 'trading_volume'), currency),
    },
    { label: t('showcase.profitFactor'), value: numberText(fieldNumber(block, 'profit_factor'), 2) },
    {
      label: t('showcase.maxDrawdown'),
      value: drawdownText(
        fieldNumber(block, 'max_drawdown_ratio'),
        fieldNumber(block, 'max_drawdown_abs'),
        currency,
      ),
      accent: 'loss',
    },
    {
      label: t('showcase.metricCurrentDrawdown'),
      value: drawdownText(
        fieldNumber(block, 'current_drawdown_ratio'),
        fieldNumber(block, 'current_drawdown_abs'),
        currency,
      ),
      accent: 'loss',
    },
  ];
}

/**
 * Starting capital used to turn a ratio profit curve into absolute amounts.
 * Taken from the payload when published, otherwise derived from an absolute /
 * ratio profit pair (both describe the same set of trades).
 */
function capitalBase(block: ShowcaseBlock): number | undefined {
  const explicit = fieldNumber(block, 'starting_capital');
  if (explicit !== undefined && explicit > 0) return explicit;
  const abs = fieldNumber(block, 'profit_total_abs');
  const ratio = fieldNumber(block, 'profit_total_ratio');
  if (abs !== undefined && ratio !== undefined && ratio !== 0) return Math.abs(abs / ratio);
  return undefined;
}

/**
 * Feed `CumProfitChart` what it expects: an ascending `{date, profit}` list
 * whose `profit` is an *absolute* amount in the stake currency, so the y-axis
 * stays on the dashboard's USDT scale instead of showing a ratio curve
 * (-0.04 … 0.02).
 *
 * A bot that publishes its curve as ratios (|value| <= 1) while still exposing
 * its capital base is rescaled here; anything else is passed through untouched.
 */
function profitHistory(block: ShowcaseBlock): CumProfitChartData[] {
  const raw = block.payload?.profit_history;
  if (!Array.isArray(raw)) return [];
  const points: { date: number; profit: number }[] = [];
  for (const point of raw) {
    const date = typeof point?.date === 'number' ? point.date : undefined;
    const value =
      typeof point?.profit_abs === 'number'
        ? point.profit_abs
        : typeof point?.profit === 'number'
          ? point.profit
          : undefined;
    if (date === undefined || value === undefined || !Number.isFinite(value)) continue;
    points.push({ date, profit: value });
  }
  points.sort((a, b) => a.date - b.date);
  const base = capitalBase(block);
  const isRatioCurve =
    points.length > 0 &&
    points.every((point) => Math.abs(point.profit) <= RATIO_HISTORY_CEILING);
  if (isRatioCurve && base !== undefined) {
    return points.map((point) => ({ date: point.date, profit: point.profit * base }));
  }
  return points;
}

/**
 * The chart projects the open P&L as a second, dotted series, derived from a
 * list of open trades. A single synthetic aggregate entry carries the payload's
 * `open_profit_abs` - no pair, stake amount or per-trade detail is involved.
 */
function chartOpenTrades(block: ShowcaseBlock): Trade[] {
  const openProfit = fieldNumber(block, 'open_profit_abs') ?? fieldNumber(block, 'profit_open_abs');
  if (openProfit === undefined || openProfit === 0) return [];
  const history = profitHistory(block);
  const lastDate = history.length > 0 ? history[history.length - 1]!.date : Date.now();
  return [
    {
      open_timestamp: lastDate,
      profit_abs: openProfit,
      total_profit_abs: openProfit,
    } as unknown as Trade,
  ];
}

function buildView(block: ShowcaseBlock): BlockView {
  return {
    block,
    title: blockTitle(block),
    row: overviewRow(block),
    roi: roiCards(block),
    metrics: metricItems(block),
    history: profitHistory(block),
    chartOpenTrades: chartOpenTrades(block),
    updatedText:
      block.updatedAt === null ? '' : t('showcase.updated', { time: timestampms(block.updatedAt) }),
  };
}

const views = computed<BlockView[]>(() => blocks.value.map(buildView));

const overviewColumns = computed<TableColumn<OverviewRow>[]>(() => [
  { accessorKey: 'label', header: t('showcase.nameLabel') },
  { accessorKey: 'status', header: t('showcase.status') },
  { accessorKey: 'trades', header: t('showcase.tradesLabel') },
  { id: 'profitOpen', header: t('showcase.openProfitLabel') },
  { id: 'profitClosed', header: t('showcase.closedProfitLabel') },
  { accessorKey: 'balance', header: t('showcase.balanceLabel') },
  { id: 'winVsLoss', header: t('showcase.winLossLabel') },
]);
</script>

<template>
  <div class="mx-auto flex h-full max-w-7xl flex-col gap-5 py-4 sm:py-6">
    <header class="flex flex-wrap items-center justify-between gap-3 px-1">
      <div class="flex items-center gap-3">
        <AppIcon class="h-9 w-9" />
        <div class="text-left">
          <h1 class="text-lg font-semibold">{{ t('showcase.pageTitle') }}</h1>
          <p class="text-xs text-neutral-500 dark:text-neutral-400">
            {{ t('showcase.refreshed', { seconds: POLL_INTERVAL_MS / 1000 }) }}
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <ThemeSelect />
        <LanguageSelect compact />
        <UButton to="/login" icon="mdi:login" size="sm">{{ t('showcase.login') }}</UButton>
      </div>
    </header>

    <section v-for="view in views" :key="view.block.key" class="flex flex-col gap-3">
      <article v-if="view.block.state === 'disabled'" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ view.title }}</h2>
        <p class="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
          {{ t('showcase.blockDisabled') }}
        </p>
      </article>

      <article v-else-if="view.block.state === 'error'" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ view.title }}</h2>
        <p class="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
          {{ t('showcase.blockError') }}
        </p>
        <UButton class="mt-4" icon="mdi:refresh" @click="retryBlock(view.block)">
          {{ t('showcase.retry') }}
        </UButton>
      </article>

      <article v-else-if="!view.block.payload" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ view.title }}</h2>
        <p class="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          {{ t('showcase.loading') }}
        </p>
      </article>

      <!-- The dashboard's first screen, minus everything that would leak: no
           pair column and no open-trade detail table. -->
      <div
        v-else
        class="showcase-overview grid min-h-full grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.04fr)_minmax(420px,0.96fr)] lg:items-start"
      >
        <div class="flex min-w-0 flex-col gap-4">
          <section class="ckq-glass-card overflow-hidden px-3 py-3">
            <h3 class="mb-2 text-left text-sm font-semibold">{{ t('showcase.overview') }}</h3>
            <div class="overflow-x-auto">
              <UTable
                :data="[view.row]"
                :columns="overviewColumns"
                :ui="{ td: 'px-2 py-2 text-default text-sm text-left whitespace-nowrap' }"
              >
                <template #label-cell="{ row }">
                  <div class="flex flex-row items-center gap-2">
                    <span class="font-medium">{{ row.original.label }}</span>
                    <UBadge v-if="row.original.runmode" color="neutral" variant="subtle">
                      {{ row.original.runmode }}
                    </UBadge>
                  </div>
                </template>
                <template #status-cell="{ row }">
                  <span class="showcase-status-pill" :class="row.original.statusClass">
                    {{ row.original.status }}
                  </span>
                </template>
                <template #profitOpen-cell="{ row }">
                  <ProfitPill
                    v-if="row.original.profitOpen !== undefined"
                    :profit-ratio="row.original.profitOpenRatio"
                    :profit-abs="row.original.profitOpen"
                    :stake-currency="row.original.balanceCurrency"
                  />
                  <span v-else>{{ MISSING }}</span>
                </template>
                <template #profitClosed-cell="{ row }">
                  <ProfitPill
                    v-if="row.original.profitClosed !== undefined"
                    :profit-ratio="row.original.profitClosedRatio"
                    :profit-abs="row.original.profitClosed"
                    :stake-currency="row.original.balanceCurrency"
                  />
                  <span v-else>{{ MISSING }}</span>
                </template>
                <template #balance-cell="{ row }">
                  <div v-if="row.original.balance !== undefined" class="tabular-nums">
                    <span>{{ formatPrice(row.original.balance, 3) }}</span>
                    <span class="ms-1 text-sm">{{ row.original.balanceCurrency }}</span>
                  </div>
                  <span v-else>{{ MISSING }}</span>
                </template>
                <template #winVsLoss-cell="{ row }">
                  <div class="tabular-nums">
                    <span class="text-profit">{{ countText(row.original.winCount) }}</span>
                    /
                    <span class="text-loss">{{ countText(row.original.lossCount) }}</span>
                  </div>
                </template>
              </UTable>
            </div>
          </section>

          <section class="space-y-3">
            <div class="grid gap-3 md:grid-cols-2">
              <article
                v-for="item in view.roi"
                :key="item.label"
                class="overview-stat-card relative overflow-hidden rounded-xl border border-default/60 bg-elevated/55 p-4"
              >
                <div
                  class="absolute inset-y-0 left-0 w-1"
                  :class="item.positive ? 'bg-emerald-500' : 'bg-rose-500'"
                />
                <p class="text-center text-sm font-semibold uppercase tracking-wide">
                  {{ item.label }}
                </p>
                <div class="mt-2 flex flex-col items-center gap-1">
                  <strong
                    class="text-2xl tabular-nums"
                    :class="item.positive ? 'text-emerald-400' : 'text-rose-400'"
                  >
                    {{ item.value }}
                  </strong>
                  <span class="text-sm tabular-nums text-muted">{{ item.sum }}</span>
                </div>
                <p class="mt-1 text-center text-sm tabular-nums text-muted">{{ item.fiat }}</p>
              </article>
            </div>

            <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              <article
                v-for="item in view.metrics"
                :key="item.label"
                class="overview-stat-card min-w-0 rounded-lg border border-default/50 bg-default/25 px-3.5 py-3"
              >
                <p class="text-left text-sm font-medium text-muted">{{ item.label }}</p>
                <p
                  class="mt-1.5 break-words text-left text-base font-semibold leading-snug tabular-nums"
                  :class="{
                    'text-profit': item.accent === 'profit',
                    'text-loss': item.accent === 'loss',
                  }"
                >
                  {{ item.value }}
                </p>
              </article>
            </div>
          </section>
        </div>

        <section
          class="profit-curve h-[360px] min-h-[360px] rounded-xl border border-default/60 bg-default/20 p-2 lg:h-[620px] lg:min-h-[620px]"
        >
          <div class="flex items-center justify-between px-2 pt-1">
            <h3 class="text-sm font-semibold">{{ t('showcase.profitCurve') }}</h3>
            <span class="text-xs text-muted">{{ view.title }}</span>
          </div>
          <div class="h-[320px] min-h-[320px] lg:h-[580px] lg:min-h-[580px]">
            <CumProfitChart
              :trades="NO_TRADES"
              :open-trades="view.chartOpenTrades"
              :profit-history="view.history"
              profit-column="profit_abs"
              :show-title="false"
            />
          </div>
        </section>
      </div>

      <p
        v-if="view.updatedText"
        class="px-1 text-left text-xs text-neutral-500 dark:text-neutral-400"
      >
        {{ view.updatedText }}
      </p>
    </section>
  </div>
</template>

<style scoped>
.showcase-overview {
  background:
    radial-gradient(circle at 12% 0%, rgb(16 185 129 / 8%), transparent 34%),
    radial-gradient(circle at 88% 32%, rgb(59 130 246 / 8%), transparent 36%);
}

.overview-stat-card {
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease;
}

.overview-stat-card:hover {
  border-color: rgb(59 130 246 / 78%);
  background-color: rgb(59 130 246 / 7%);
  box-shadow:
    0 0 0 1px rgb(59 130 246 / 20%),
    0 8px 24px rgb(15 23 42 / 18%);
}

.showcase-status-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

.showcase-status-pill--running {
  color: #059669;
  background: color-mix(in srgb, #10b981 18%, transparent);
}

.showcase-status-pill--stopped {
  color: #e11d48;
  background: color-mix(in srgb, #f43f5e 18%, transparent);
}

.showcase-status-pill--unknown {
  color: var(--ckq-muted);
  background: color-mix(in srgb, var(--ckq-muted) 16%, transparent);
}
</style>
