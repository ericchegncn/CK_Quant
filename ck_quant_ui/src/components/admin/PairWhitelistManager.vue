<script setup lang="ts">
import type { AdminMarketsResponse } from '@/types';
import {
  filterAdminMarkets,
  setPairWhitelisted,
  sortAdminMarkets,
  type AdminMarketSort,
} from '@/utils/adminMarkets';
import { useI18n } from 'vue-i18n';

const props = defineProps<{
  marketData?: AdminMarketsResponse;
  whitelist: string[];
  loading?: boolean;
  error?: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  'update:whitelist': [value: string[]];
}>();

const { locale, t } = useI18n();
const search = ref('');
const sort = ref<AdminMarketSort>('volume');

const sortItems = computed(() => [
  { label: t('admin.sortVolume'), value: 'volume' },
  { label: t('admin.sortGainers'), value: 'gainers' },
  { label: t('admin.sortLosers'), value: 'losers' },
]);

const visibleMarkets = computed(() =>
  sortAdminMarkets(filterAdminMarkets(props.marketData?.markets ?? [], search.value), sort.value),
);
const selected = computed(() => new Set(props.whitelist));
const hasPatternWhitelist = computed(() =>
  props.whitelist.some((pair) => /[.*+?^${}()|[\]\\]/.test(pair)),
);

function setSelected(pair: string, value: boolean) {
  if (props.disabled) return;
  emit('update:whitelist', setPairWhitelisted(props.whitelist, pair, value));
}

function formatPrice(value: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat(locale.value, {
    maximumFractionDigits: value >= 100 ? 2 : value >= 1 ? 4 : 8,
  }).format(value);
}

function formatVolume(value: number | null) {
  if (value == null) return '—';
  return new Intl.NumberFormat(locale.value, {
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercentage(value: number | null) {
  if (value == null) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 class="font-semibold">{{ t('admin.marketSelectorTitle') }}</h2>
          <p class="text-muted mt-1 text-sm">
            {{ t('admin.marketSelectorDescription') }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <UInput
            v-model="search"
            icon="mdi:magnify"
            :placeholder="t('admin.searchPairs')"
            class="min-w-48 flex-1"
          />
          <USelect
            v-model="sort"
            :items="sortItems"
            label-key="label"
            value-key="value"
            class="min-w-44"
          />
          <UButton
            color="neutral"
            variant="outline"
            icon="mdi:refresh"
            :label="t('admin.refreshMarkets')"
            :loading="loading"
            @click="emit('refresh')"
          />
        </div>
      </div>
    </template>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="mdi:alert-circle-outline"
      :description="error"
      class="mb-4"
    />

    <UAlert
      v-if="hasPatternWhitelist"
      color="warning"
      variant="subtle"
      icon="mdi:regex"
      :description="t('admin.whitelistPatternWarning')"
      class="mb-4"
    />

    <div class="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.8fr)]">
      <section class="min-w-0 overflow-hidden rounded-lg border border-default">
        <div
          class="bg-elevated/80 text-muted grid grid-cols-[32px_minmax(112px,1fr)_minmax(78px,0.8fr)_70px] items-center gap-2 border-b border-default px-3 py-2 text-xs font-semibold sm:grid-cols-[36px_minmax(170px,1fr)_minmax(110px,0.7fr)_minmax(120px,0.8fr)_90px]"
        >
          <span></span>
          <span>{{ t('admin.pair') }}</span>
          <span class="hidden text-right sm:block">{{ t('admin.lastPrice') }}</span>
          <span class="text-right">{{ t('admin.quoteVolume24h') }}</span>
          <span class="text-right">{{ t('admin.change24h') }}</span>
        </div>

        <div class="h-[560px] overflow-y-auto overscroll-contain md:h-[760px]">
          <div v-if="loading && !marketData" class="flex h-full items-center justify-center">
            <UIcon name="mdi:loading" class="text-muted size-8 animate-spin" />
          </div>
          <div
            v-else-if="visibleMarkets.length === 0"
            class="text-muted flex h-full items-center justify-center px-4 text-sm"
          >
            {{ t('admin.noMarkets') }}
          </div>
          <template v-else>
            <label
              v-for="market in visibleMarkets"
              :key="market.pair"
              class="hover:bg-elevated/60 grid min-h-9 cursor-pointer grid-cols-[32px_minmax(112px,1fr)_minmax(78px,0.8fr)_70px] items-center gap-2 border-b border-default/70 px-3 py-1.5 text-sm last:border-b-0 sm:grid-cols-[36px_minmax(170px,1fr)_minmax(110px,0.7fr)_minmax(120px,0.8fr)_90px]"
            >
              <UCheckbox
                :model-value="selected.has(market.pair)"
                :disabled="disabled"
                @update:model-value="setSelected(market.pair, $event === true)"
              />
              <span class="min-w-0 truncate font-medium" :title="market.pair">{{
                market.pair
              }}</span>
              <span class="hidden truncate text-right tabular-nums sm:block">
                {{ formatPrice(market.last) }}
              </span>
              <span class="truncate text-right tabular-nums">
                {{ formatVolume(market.quote_volume) }}
              </span>
              <span
                class="text-right font-medium tabular-nums"
                :class="
                  market.percentage === null
                    ? 'text-muted'
                    : market.percentage >= 0
                      ? 'text-success'
                      : 'text-error'
                "
              >
                {{ formatPercentage(market.percentage) }}
              </span>
            </label>
          </template>
        </div>

        <div
          class="text-muted flex flex-wrap justify-between gap-2 border-t border-default px-3 py-2 text-xs"
        >
          <span>
            {{
              t('admin.marketCount', {
                visible: visibleMarkets.length,
                total: marketData?.markets.length ?? 0,
              })
            }}
          </span>
          <span v-if="marketData">
            {{ marketData.exchange }} · {{ marketData.stake_currency }}
          </span>
        </div>
      </section>

      <section class="flex min-w-0 flex-col rounded-lg border border-default">
        <div class="border-b border-default px-3 py-2">
          <h3 class="font-semibold">{{ t('admin.currentWhitelist') }}</h3>
          <p class="text-muted mt-1 text-xs">
            {{ t('admin.whitelistDraftHint') }}
          </p>
        </div>
        <div class="max-h-[560px] min-h-48 overflow-y-auto overscroll-contain md:max-h-[760px]">
          <p v-if="whitelist.length === 0" class="text-muted p-4 text-sm">
            {{ t('admin.emptyWhitelist') }}
          </p>
          <template v-else>
            <label
              v-for="pair in whitelist"
              :key="pair"
              class="hover:bg-elevated/60 flex min-h-9 cursor-pointer items-center gap-3 border-b border-default/70 px-3 py-1.5 text-sm last:border-b-0"
            >
              <UCheckbox
                :model-value="true"
                :disabled="disabled"
                @update:model-value="setSelected(pair, $event === true)"
              />
              <span class="min-w-0 truncate font-medium" :title="pair">{{ pair }}</span>
            </label>
          </template>
        </div>
        <div class="text-muted mt-auto border-t border-default px-3 py-2 text-xs">
          {{ t('admin.selectedCount', { count: whitelist.length }) }}
        </div>
      </section>
    </div>
  </UCard>
</template>
