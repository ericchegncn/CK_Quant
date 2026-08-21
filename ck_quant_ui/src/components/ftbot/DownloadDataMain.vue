<script setup lang="ts">
import type { DownloadDataPayload, ExchangeSelection } from '@/types';
import { useI18n } from 'vue-i18n';
import { MarginMode, TradingMode } from '@/types';
import type { SelectMenuItem } from '@nuxt/ui';

const botStore = useBotStore();
const pairlistStore = usePairlistConfigStore();
const { t } = useI18n();
const pairs = ref<string[]>(['BTC/USDT', 'ETH/USDT', '']);
const timeframes = ref<string[]>(['5m', '1h']);

const timeSelection = ref({
  useCustomTimerange: false,
  timerange: '',
  days: 30,
});

const { pairTemplates } = usePairTemplates();

const exchange = ref<{
  customExchange: boolean;
  selectedExchange: ExchangeSelection;
}>({
  customExchange: false,
  selectedExchange: {
    exchange: 'binance',
    trade_mode: {
      margin_mode: MarginMode.NONE,
      trading_mode: TradingMode.SPOT,
    },
  },
});

const advancedOptions = ref({
  erase: false,
  prepend_data: false,
  downloadTrades: false,
  candleTypes: [] as string[],
});

// State to track the collapse status
const isAdvancedOpen = ref(false);
const candleTypes = computed<SelectMenuItem[]>(() => [
  { label: t('research.spot'), value: 'spot' },
  { label: t('research.futures'), value: 'futures' },
  { label: t('research.fundingRate'), value: 'funding_rate' },
  { label: t('research.mark'), value: 'mark' },
  { label: t('research.index'), value: 'index' },
  { label: t('research.premiumIndex'), value: 'premiumIndex' },
]);

function addPairs(_pairs: string[]) {
  pairs.value.push(..._pairs);
}

function replacePairs(_pairs: string[]) {
  pairs.value = [..._pairs];
}

async function startDownload() {
  const payload: DownloadDataPayload = {
    pairs: pairs.value.filter((pair) => pair !== ''),
    timeframes: timeframes.value.filter((tf) => tf !== ''),
  };

  // Add either timerange or days to the payload
  if (timeSelection.value.useCustomTimerange && timeSelection.value.timerange) {
    payload.timerange = timeSelection.value.timerange;
  } else {
    payload.days = timeSelection.value.days;
  }

  // Include advanced options only if the section is open
  if (isAdvancedOpen.value) {
    payload.erase = advancedOptions.value.erase;
    payload.download_trades = advancedOptions.value.downloadTrades;

    if (exchange.value.customExchange) {
      payload.exchange = exchange.value.selectedExchange.exchange;
      payload.trading_mode = exchange.value.selectedExchange.trade_mode.trading_mode;
      payload.margin_mode = exchange.value.selectedExchange.trade_mode.margin_mode;
    }
    if (
      botStore.activeBot.botFeatures.downloadDataCandleTypes &&
      advancedOptions.value.candleTypes.length > 0
    ) {
      payload.candle_types = advancedOptions.value.candleTypes;
    }
    if (botStore.activeBot.botFeatures.downloadDataPrepend && advancedOptions.value.prepend_data) {
      payload.prepend_data = true;
    }
  }

  await botStore.activeBot.startDataDownload(payload);
}
</script>

<template>
  <div class="px-1 mx-auto w-full max-w-4xl lg:max-w-7xl">
    <BackgroundJobTracking class="mb-4" />
    <DraggableContainer :header="t('research.downloadingData')" class="mx-1 p-4">
      <div class="flex mb-3 gap-3 flex-col">
        <div class="flex flex-col gap-3">
          <div class="flex flex-col lg:flex-row gap-3">
            <!-- Pairs section - keeping template buttons next to input -->
            <div class="flex-fill">
              <div class="flex flex-col gap-2">
                <div class="flex justify-between">
                  <h4 class="text-start font-bold text-lg">{{ t('research.selectPairs') }}</h4>
                  <h5 class="text-start font-bold text-lg">{{ t('research.pairsFromTemplate') }}</h5>
                </div>
                <div class="flex gap-2">
                  <BaseStringList v-model="pairs" :placeholder="t('research.pair')" class="grow" />
                  <div class="flex flex-col gap-1">
                    <div class="flex flex-col gap-1">
                      <UButton
                        v-for="pt in pairTemplates"
                        :key="pt.idx"
                        color="neutral"
                        :title="pt.pairs.reduce((acc, p) => `${acc}${p}\n`, '')"
                        @click="addPairs(pt.pairs)"
                      >
                        {{ pt.description }}
                      </UButton>
                    </div>
                    <USeparator />
                    <UButton
                      :disabled="pairlistStore.whitelist.length === 0"
                      :title="t('research.addPairlistPairsHint')"
                      color="neutral"
                      @click="replacePairs(pairlistStore.whitelist)"
                    >
                      {{ t('research.usePairlistPairs') }}
                    </UButton>
                  </div>
                </div>
              </div>
            </div>

            <!-- Timeframes section -->
            <div class="flex-fill px-3">
              <div class="flex flex-col gap-2">
                <h4 class="text-start font-bold text-lg">{{ t('research.selectTimeframes') }}</h4>
                <BaseStringList v-model="timeframes" :placeholder="t('research.timeframe')" />
              </div>
            </div>
          </div>

          <!-- Time selection section -->
          <div class="px-3 border dark:border-neutral-700 border-neutral-300 p-2 rounded-sm">
            <div class="flex flex-col gap-2">
              <div class="flex justify-between items-center">
                <h4 class="text-start mb-0 font-bold text-lg">{{ t('research.timeSelection') }}</h4>
                <BaseCheckbox v-model="timeSelection.useCustomTimerange" class="mb-0" switch>
                  {{ t('research.useCustomTimerange') }}
                </BaseCheckbox>
              </div>

              <div v-if="timeSelection.useCustomTimerange">
                <TimeRangeSelect v-model="timeSelection.timerange" />
              </div>
              <div v-else class="flex items-center gap-2">
                <label>{{ t('research.daysToDownload') }}:</label>
                <UInputNumber
                  v-model="timeSelection.days"
                  :aria-label="t('research.daysToDownload')"
                  :min="1"
                  :step="1"
                />
              </div>
            </div>
          </div>
          <!-- Advanced options section -->
          <BaseCollapsible :title="t('research.advancedOptions')" v-model:open="isAdvancedOpen">
            <UAlert
              color="info"
              class="my-2 py-2"
              :description="t('research.advancedOptionsHint')"
            />
            <div
              class="mb-2 border dark:border-neutral-700 border-neutral-300 rounded-md p-2 text-start"
            >
              <BaseCheckbox v-model="advancedOptions.erase" class="mb-2"
                >{{ t('research.eraseExistingData') }}</BaseCheckbox
              >
              <BaseCheckbox
                v-model="advancedOptions.prepend_data"
                class="mb-2"
                v-if="botStore.activeBot.botFeatures.downloadDataPrepend"
                >{{ t('research.prependData') }}</BaseCheckbox
              >
              <BaseCheckbox v-model="advancedOptions.downloadTrades" class="mb-2">
                {{ t('research.downloadTradesInstead') }}
              </BaseCheckbox>
              <div class="grid grid-cols md:grid-cols-2 items-center gap-2">
                <USelectMenu
                  multiple
                  v-if="botStore.activeBot.botFeatures.downloadDataCandleTypes"
                  v-model="advancedOptions.candleTypes"
                  :items="candleTypes"
                  :placeholder="t('research.selectCandleTypes')"
                  value-key="value"
                />
                <small>{{ t('research.candleTypesHint') }}</small>
              </div>
            </div>
            <div
              class="mb-2 border dark:border-neutral-700 border-neutral-300 rounded-md p-2 text-start"
            >
              <UCollapsible v-model:open="exchange.customExchange">
                <BaseCheckbox v-model="exchange.customExchange" class="mb-2">
                  {{ t('research.customExchange') }}
                </BaseCheckbox>
                <template #content>
                  <ExchangeSelect
                    v-show="exchange.customExchange"
                    v-model="exchange.selectedExchange"
                  />
                </template>
              </UCollapsible>
            </div>
          </BaseCollapsible>

          <div class="px-3">
            <UButton variant="solid" icon="mdi:download" @click="startDownload"
              >{{ t('research.startDownload') }}</UButton
            >
          </div>
        </div>
      </div>
    </DraggableContainer>
  </div>
</template>
