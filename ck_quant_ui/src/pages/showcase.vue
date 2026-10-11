<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import axios from 'axios';

import type { ClosedTrade, CumProfitChartData, Trade } from '@/types';

const { t } = useI18n();

definePage({
  meta: {
    allowAnonymous: true,
  },
});

const POLL_INTERVAL_MS = 60_000;
const OVERVIEW_ENDPOINT = '/api/v1/public/overview';

/**
 * Tolerant shape of the public overview payload. The server may expose the
 * metrics either flat or nested below a `profit` / `summary` object, so every
 * field stays optional and is read through `resolveField()`.
 */
interface PublicOverviewPayload {
  running?: boolean;
  status?: string;
  state?: string;
  label?: string;
  exchange?: string;
  exchange_name?: string;
  uptime_seconds?: number;
  start_date?: string;
  bot_start_date?: string;
  version?: string;
  open_trade_count?: number;
  open_trades?: number;
  trade_count?: number;
  winrate?: number;
  profit_factor?: number | null;
  expectancy?: number;
  expectancy_ratio?: number;
  max_drawdown?: number;
  profit_total_ratio?: number;
  profit_all_ratio?: number;
  profit_abs?: number;
  profit_all_coin?: number;
  show_absolute?: boolean;
  stake_currency?: string;
  profit_history?: CumProfitChartData[];
  profit?: PublicOverviewPayload;
  summary?: PublicOverviewPayload;
}

interface ShowcaseMetric {
  label: string;
  value: string;
  accent?: 'profit' | 'loss';
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

function resolveField<K extends keyof PublicOverviewPayload>(
  block: ShowcaseBlock,
  key: K,
): PublicOverviewPayload[K] | undefined {
  const source = block.payload;
  if (!source) return undefined;
  const direct = source[key];
  if (direct !== undefined && direct !== null) return direct;
  for (const nested of [source.profit, source.summary]) {
    if (!nested) continue;
    const value = nested[key];
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
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

// Stable empty collections: passing inline literals would re-create arrays on
// every render and make the chart recompute for no reason.
const NO_TRADES: ClosedTrade[] = [];
const NO_OPEN_TRADES: Trade[] = [];

function blockTitle(block: ShowcaseBlock): string {
  const label = resolveField(block, 'label');
  return typeof label === 'string' && label ? label : t('showcase.defaultLabel');
}

function blockExchange(block: ShowcaseBlock): string {
  const value = resolveField(block, 'exchange') ?? resolveField(block, 'exchange_name');
  return typeof value === 'string' && value ? value : 'N/A';
}

function blockVersion(block: ShowcaseBlock): string {
  const value = resolveField(block, 'version');
  return typeof value === 'string' && value ? value : 'N/A';
}

function blockStakeCurrency(block: ShowcaseBlock): string {
  const value = resolveField(block, 'stake_currency');
  return typeof value === 'string' && value ? value : 'USDT';
}

function blockRunning(block: ShowcaseBlock): boolean | undefined {
  const explicit = resolveField(block, 'running');
  if (typeof explicit === 'boolean') return explicit;
  const raw = resolveField(block, 'status') ?? resolveField(block, 'state');
  if (typeof raw !== 'string' || !raw) return undefined;
  const normalized = raw.toLowerCase();
  if (normalized.includes('run') || normalized === 'online') return true;
  if (normalized.includes('stop') || normalized === 'offline') return false;
  return undefined;
}

function blockStatusText(block: ShowcaseBlock): string {
  const running = blockRunning(block);
  if (running === true) return t('showcase.running');
  if (running === false) return t('showcase.stopped');
  return t('showcase.unknown');
}

function blockStatusClass(block: ShowcaseBlock): string {
  const running = blockRunning(block);
  if (running === true) return 'showcase-status-pill--running';
  if (running === false) return 'showcase-status-pill--stopped';
  return 'showcase-status-pill--unknown';
}

function blockUptime(block: ShowcaseBlock): string {
  const seconds = resolveField(block, 'uptime_seconds');
  if (typeof seconds === 'number' && Number.isFinite(seconds)) {
    return humanizeDurationFromSeconds(seconds);
  }
  const startDate = resolveField(block, 'start_date') ?? resolveField(block, 'bot_start_date');
  if (typeof startDate === 'string' && startDate) {
    const started = Date.parse(startDate);
    if (!Number.isNaN(started)) {
      return humanizeDurationFromSeconds(Math.max(0, (Date.now() - started) / 1000));
    }
  }
  return 'N/A';
}

function blockTotalReturn(block: ShowcaseBlock): number | undefined {
  const value = resolveField(block, 'profit_total_ratio') ?? resolveField(block, 'profit_all_ratio');
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function blockAbsoluteProfit(block: ShowcaseBlock): number | undefined {
  const value = resolveField(block, 'profit_abs') ?? resolveField(block, 'profit_all_coin');
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function blockShowAbsolute(block: ShowcaseBlock): boolean {
  return (
    blockAbsoluteProfit(block) !== undefined && resolveField(block, 'show_absolute') !== false
  );
}

function blockTotalReturnText(block: ShowcaseBlock): string {
  const value = blockTotalReturn(block);
  return value === undefined ? 'N/A' : formatPercent(value, 2);
}

function blockTotalReturnClass(block: ShowcaseBlock): string {
  const value = blockTotalReturn(block);
  if (value === undefined) return '';
  return value >= 0 ? 'text-emerald-500' : 'text-rose-500';
}

function blockAbsoluteProfitText(block: ShowcaseBlock): string {
  const value = blockAbsoluteProfit(block);
  return value === undefined ? 'N/A' : `${formatPrice(value, 3)} ${blockStakeCurrency(block)}`;
}

function blockUpdatedText(block: ShowcaseBlock): string {
  return block.updatedAt === null
    ? ''
    : t('showcase.updated', { time: timestampms(block.updatedAt) });
}

function blockProfitHistory(block: ShowcaseBlock): CumProfitChartData[] {
  const history = resolveField(block, 'profit_history');
  return Array.isArray(history) ? history : [];
}

function numberOrNa(value: unknown, decimals = 0): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? formatNumber(value, decimals)
    : 'N/A';
}

function blockMetrics(block: ShowcaseBlock): ShowcaseMetric[] {
  const openTrades = resolveField(block, 'open_trade_count') ?? resolveField(block, 'open_trades');
  const tradeCount = resolveField(block, 'trade_count');
  const winrate = resolveField(block, 'winrate');
  const profitFactor = resolveField(block, 'profit_factor');
  const expectancy = resolveField(block, 'expectancy');
  const expectancyRatio = resolveField(block, 'expectancy_ratio');
  const maxDrawdown = resolveField(block, 'max_drawdown');

  return [
    { label: t('showcase.exchange'), value: blockExchange(block) },
    { label: t('showcase.uptime'), value: blockUptime(block) },
    { label: t('showcase.version'), value: blockVersion(block) },
    { label: t('showcase.openTrades'), value: numberOrNa(openTrades, 0) },
    { label: t('showcase.tradeCount'), value: numberOrNa(tradeCount, 0) },
    {
      label: t('showcase.winRate'),
      value: typeof winrate === 'number' ? formatPercent(winrate, 2) : 'N/A',
      accent: typeof winrate === 'number' && winrate >= 0.5 ? 'profit' : undefined,
    },
    {
      label: t('showcase.profitFactor'),
      value: typeof profitFactor === 'number' ? formatNumber(profitFactor, 2) : 'N/A',
      accent: typeof profitFactor === 'number' && profitFactor >= 1 ? 'profit' : undefined,
    },
    {
      label: t('showcase.expectancy'),
      value:
        typeof expectancy === 'number'
          ? `${formatNumber(expectancy, 2)}${
              typeof expectancyRatio === 'number'
                ? ` (${formatNumber(expectancyRatio, 2)})`
                : ''
            }`
          : 'N/A',
    },
    {
      label: t('showcase.maxDrawdown'),
      value: typeof maxDrawdown === 'number' ? formatPercent(maxDrawdown, 2) : 'N/A',
      accent: 'loss',
    },
  ];
}
</script>

<template>
  <div class="mx-auto flex h-full max-w-6xl flex-col gap-4 py-4 sm:py-6">
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

    <section v-for="block in blocks" :key="block.key" class="flex flex-col gap-4">
      <article v-if="block.state === 'disabled'" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ blockTitle(block) }}</h2>
        <p class="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
          {{ t('showcase.blockDisabled') }}
        </p>
      </article>

      <article v-else-if="block.state === 'error'" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ blockTitle(block) }}</h2>
        <p class="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
          {{ t('showcase.blockError') }}
        </p>
        <UButton class="mt-4" icon="mdi:refresh" @click="retryBlock(block)">
          {{ t('showcase.retry') }}
        </UButton>
      </article>

      <article v-else-if="!block.payload" class="ckq-glass-card p-6 text-left">
        <h2 class="text-lg font-semibold">{{ blockTitle(block) }}</h2>
        <p class="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          {{ t('showcase.loading') }}
        </p>
      </article>

      <div v-else class="grid gap-4 lg:grid-cols-2 lg:items-start">
        <article class="ckq-glass-card p-5 text-left">
          <div class="mb-4 flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold">{{ blockTitle(block) }}</h2>
            <span
              class="showcase-status-pill"
              :class="blockStatusClass(block)"
              :title="t('showcase.status')"
            >
              {{ blockStatusText(block) }}
            </span>
          </div>
          <div class="grid gap-2 sm:grid-cols-2">
            <div class="showcase-stat">
              <p class="text-xs font-medium text-muted">{{ t('showcase.totalProfit') }}</p>
              <p class="showcase-stat-value" :class="blockTotalReturnClass(block)">
                {{ blockTotalReturnText(block) }}
              </p>
            </div>
            <div v-if="blockShowAbsolute(block)" class="showcase-stat">
              <p class="text-xs font-medium text-muted">{{ t('showcase.absoluteProfit') }}</p>
              <p class="showcase-stat-value" :class="blockTotalReturnClass(block)">
                {{ blockAbsoluteProfitText(block) }}
              </p>
            </div>
            <div v-for="item in blockMetrics(block)" :key="item.label" class="showcase-stat">
              <p class="text-xs font-medium text-muted">{{ item.label }}</p>
              <p
                class="showcase-stat-value"
                :class="{
                  'text-emerald-500': item.accent === 'profit',
                  'text-rose-500': item.accent === 'loss',
                }"
              >
                {{ item.value }}
              </p>
            </div>
          </div>
          <p
            v-if="blockUpdatedText(block)"
            class="mt-3 text-xs text-neutral-500 dark:text-neutral-400"
          >
            {{ blockUpdatedText(block) }}
          </p>
        </article>

        <article class="ckq-glass-card p-4 text-left">
          <h2 class="mb-2 px-1 text-base font-semibold">{{ t('showcase.profitCurve') }}</h2>
          <div class="h-[320px] min-h-[320px] lg:h-[460px] lg:min-h-[460px]">
            <CumProfitChart
              :profit-history="blockProfitHistory(block)"
              :trades="NO_TRADES"
              :open-trades="NO_OPEN_TRADES"
              profit-column="profit"
              :show-title="false"
            />
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.showcase-stat {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--ckq-border) 72%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--ckq-glass-strong) 55%, transparent);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.showcase-stat:hover {
  border-color: color-mix(in srgb, var(--color-brand-400) 45%, var(--ckq-border));
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.12);
}

.showcase-stat-value {
  margin-top: 6px;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.35;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}

.showcase-status-pill {
  flex-shrink: 0;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
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
