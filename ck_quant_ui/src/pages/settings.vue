<script setup lang="ts">
import { FtWsMessageTypes } from '@/types/wsMessageTypes';
import axios from 'axios';
import { useI18n } from 'vue-i18n';

const settingsStore = useSettingsStore();
const colorStore = useColorStore();
const layoutStore = useLayoutStore();
const botStore = useBotStore();
const { t } = useI18n();
const localizedBacktestMetricOptions = computed(() => localizeBacktestMetricOptions(t));

// ---- Guest showcase ("public_showcase") management ------------------------
// Lets the logged-in operator decide which locally configured bots may be
// displayed on the guest page, and build a share link from their API bases.
type ShowcaseStatus = 'unknown' | 'ok' | 'unsupported' | 'error';

const showcaseStatus = reactive<Record<string, ShowcaseStatus>>({});
const showcaseEnabled = reactive<Record<string, boolean>>({});
const showcaseShowAbsolute = reactive<Record<string, boolean>>({});
const showcaseLabels = reactive<Record<string, string>>({});
const showcaseSaving = ref(false);
const shareLink = ref('');

// Display name and API base come from the local configuration. The share link
// only ever contains the API base - never a token or key.
const showcaseRows = computed(() =>
  botStore.availableBotsSorted.map((bot) => ({
    botId: bot.botId,
    name: bot.botName,
    url: bot.botUrl,
  })),
);

async function loadShowcaseSettings() {
  await Promise.all(
    showcaseRows.value.map(async (row) => {
      const bot = botStore.botStores[row.botId];
      if (!bot) {
        showcaseStatus[row.botId] = 'error';
        return;
      }
      try {
        const config = await bot.getPublicShowcase();
        showcaseEnabled[row.botId] = config.enabled ?? false;
        showcaseShowAbsolute[row.botId] = config.show_absolute ?? true;
        showcaseLabels[row.botId] = config.label ?? row.name;
        showcaseStatus[row.botId] = 'ok';
      } catch (err) {
        // Graceful degradation: a server without the endpoint (yet) only shows
        // a "enable it in the config file" hint instead of crashing.
        const status = axios.isAxiosError(err) ? err.response?.status : undefined;
        showcaseStatus[row.botId] = status === 404 || status === 501 ? 'unsupported' : 'error';
        if (showcaseLabels[row.botId] === undefined) showcaseLabels[row.botId] = row.name;
        if (showcaseShowAbsolute[row.botId] === undefined) showcaseShowAbsolute[row.botId] = true;
      }
    }),
  );
}

async function saveShowcaseSettings() {
  showcaseSaving.value = true;
  let failed = 0;
  await Promise.all(
    showcaseRows.value.map(async (row) => {
      if (showcaseStatus[row.botId] === 'unsupported') return;
      const bot = botStore.botStores[row.botId];
      if (!bot) return;
      try {
        const config = await bot.setPublicShowcase({
          enabled: showcaseEnabled[row.botId] ?? false,
          label: showcaseLabels[row.botId] ?? row.name,
          show_absolute: showcaseShowAbsolute[row.botId] ?? true,
        });
        showcaseEnabled[row.botId] = config.enabled ?? false;
        showcaseShowAbsolute[row.botId] = config.show_absolute ?? true;
        showcaseLabels[row.botId] = config.label ?? row.name;
        showcaseStatus[row.botId] = 'ok';
      } catch (err) {
        const status = axios.isAxiosError(err) ? err.response?.status : undefined;
        if (status === 404 || status === 501) {
          showcaseStatus[row.botId] = 'unsupported';
        } else {
          failed += 1;
        }
      }
    }),
  );
  showcaseSaving.value = false;
  if (failed > 0) {
    showAlert(t('settings.showcase.saveFailed'), 'error');
  } else {
    showAlert(t('settings.showcase.saved'));
  }
}

function generateShareLink() {
  const selected = showcaseRows.value
    .filter((row) => showcaseEnabled[row.botId])
    .map((row) => row.url.replace(/\/+$/, ''));
  if (selected.length === 0) {
    shareLink.value = '';
    showAlert(t('settings.showcase.noSelection'), 'warning');
    return;
  }
  const params = new URLSearchParams();
  selected.forEach((url) => params.append('api', url));
  shareLink.value = `${window.location.origin}/showcase?${params.toString()}`;
}

async function copyShareLink() {
  if (!shareLink.value) return;
  try {
    await navigator.clipboard.writeText(shareLink.value);
    showAlert(t('settings.showcase.copied'));
  } catch {
    showAlert(t('settings.showcase.copyFailed'), 'error');
  }
}

onMounted(() => void loadShowcaseSettings());

const timezoneOptions = ['UTC', Intl.DateTimeFormat().resolvedOptions().timeZone];
const openTradesOptions = computed(() => [
  { value: OpenTradeVizOptions.showPill, text: t('settings.showPill') },
  { value: OpenTradeVizOptions.asTitle, text: t('settings.showTitle') },
  { value: OpenTradeVizOptions.noOpenTrades, text: t('settings.showNone') },
]);
const colorPreferenceOptions = computed(() => [
  { value: ColorPreferences.GREEN_UP, text: t('settings.greenUp') },
  { value: ColorPreferences.RED_UP, text: t('settings.redUp') },
]);

const resetDynamicLayout = () => {
  layoutStore.resetTradingLayout();
  layoutStore.resetDashboardLayout();
  showAlert(t('settings.resetDone'));
};
</script>

<template>
  <UCard class="mx-auto mt-3 p-4 max-w-4xl">
    <template #header
      ><span class="text-2xl font-bold">{{ t('settings.title') }}</span></template
    >
    <div class="flex flex-col gap-4 text-start dark:text-neutral-300">
      <p class="text-left">{{ t('settings.uiVersion') }}: {{ settingsStore.uiVersion }}</p>

      <div class="border border-neutral-400 rounded-sm p-4 space-y-4">
        <h4 class="text-xl font-semibold">{{ t('settings.uiSettings') }}</h4>

        <div class="space-y-1">
          <label class="block text-sm">{{ t('language.label') }}</label>
          <LanguageSelect />
        </div>

        <USeparator />

        <BaseCheckbox v-model="layoutStore.layoutLocked" class="space-y-1">
          {{ t('settings.lockLayouts') }}
          <template #hint>
            {{ t('settings.lockLayoutsHint') }}
          </template>
        </BaseCheckbox>

        <div class="flex flex-row items-center gap-2 space-y-2">
          <UButton color="neutral" size="md" class="mb-0" @click="resetDynamicLayout">{{
            t('settings.resetLayout')
          }}</UButton>
          <small class="text-sm block text-neutral-600 dark:text-neutral-400">{{
            t('settings.resetLayoutHint')
          }}</small>
        </div>

        <USeparator />

        <div class="space-y-1">
          <label class="block text-sm">{{ t('settings.showOpenTrades') }}</label>
          <USelect
            v-model="settingsStore.openTradesInTitle"
            :items="openTradesOptions"
            label-key="text"
            value-key="value"
            class="w-full"
          />
          <small class="text-sm text-neutral-600 dark:text-neutral-400">{{
            t('settings.showOpenTradesHint')
          }}</small>
        </div>

        <div class="space-y-1">
          <label class="block text-sm">{{ t('settings.timezone') }}</label>
          <USelect v-model="settingsStore.timezone" :items="timezoneOptions" class="w-full" />
          <small class="text-sm text-neutral-600 dark:text-neutral-400">{{
            t('settings.timezoneHint')
          }}</small>
        </div>

        <BaseCheckbox v-model="settingsStore.backgroundSync" class="space-y-1">
          {{ t('settings.backgroundSync') }}
          <template #hint>{{ t('settings.backgroundSyncHint') }}</template>
        </BaseCheckbox>

        <BaseCheckbox v-model="settingsStore.confirmDialog" class="space-y-1">
          {{ t('settings.confirmations') }}
          <template #hint
            >{{ t('settings.confirmationsHint') }}<br />
            This will also show <i-mdi-run-fast class="text-yellow-300 inline" />
            <i-mdi-alert class="text-yellow-300 inline" />
            in the title bar.
          </template>
        </BaseCheckbox>

        <BaseCheckbox v-model="settingsStore.multiPaneButtonsShowText" class="space-y-1">
          {{ t('settings.paneButtonText') }}
          <template #hint>{{ t('settings.paneButtonTextHint') }}</template>
        </BaseCheckbox>
      </div>

      <div class="border border-neutral-400 rounded-sm p-4 space-y-4">
        <h4 class="text-lg font-semibold">{{ t('settings.chartSettings') }}</h4>

        <div class="space-y-1">
          <label class="block text-sm">{{ t('settings.chartScaleSide') }}</label>
          <URadioGroup
            v-model="settingsStore.chartLabelSide"
            :items="[
              { label: t('settings.left'), value: 'left' },
              { label: t('settings.right'), value: 'right' },
            ]"
            orientation="horizontal"
          />
          <small class="text-sm text-neutral-600 dark:text-neutral-400">
            {{ t('settings.chartScaleSide') }}
          </small>
        </div>

        <BaseCheckbox v-model="settingsStore.useHeikinAshiCandles" class="space-y-1">
          {{ t('settings.heikinAshi') }}
          <template #hint>Use Heikin Ashi candles in your charts</template>
        </BaseCheckbox>

        <BaseCheckbox v-model="settingsStore.useReducedPairCalls" class="space-y-1">
          {{ t('settings.reducedColumns') }}
          <template #hint>{{ t('settings.reducedColumnsHint') }}</template>
        </BaseCheckbox>

        <div>
          <p>{{ t('settings.candleCount') }}</p>
          <div class="flex flex-row gap-5 w-full items-center">
            <USlider
              v-model="settingsStore.chartDefaultCandleCount"
              class="flex-1"
              :step="50"
              :min="100"
              :max="2000"
            />
            <UInputNumber
              v-model="settingsStore.chartDefaultCandleCount"
              :step="50"
              :min="100"
              :max="2000"
              size="sm"
            />
          </div>
        </div>

        <div class="space-y-1">
          <label class="block">{{ t('settings.candleColors') }}</label>
          <div class="flex flex-row gap-5 items-center">
            <URadioGroup
              v-model="colorStore.colorPreference"
              :items="colorPreferenceOptions"
              label-key="text"
              value-key="value"
              orientation="horizontal"
            >
              <template #label="{ item }">
                <div class="flex items-center">
                  <span class="mr-2">{{ item.text }}</span>
                  <UIcon
                    name="mdi:arrow-up-thin"
                    :color="
                      item.value === ColorPreferences.GREEN_UP
                        ? colorStore.colorProfit
                        : colorStore.colorLoss
                    "
                    class="-ml-2 size-5"
                  />
                  <UIcon
                    name="mdi:arrow-down-thin"
                    :color="
                      item.value === ColorPreferences.GREEN_UP
                        ? colorStore.colorLoss
                        : colorStore.colorProfit
                    "
                    class="-ml-2 size-5"
                  />
                </div>
              </template>
            </URadioGroup>
          </div>
        </div>
      </div>

      <div class="border rounded-sm border-neutral-400 p-4 space-y-4">
        <h4 class="text-lg font-semibold">{{ t('settings.notifications') }}</h4>
        <div class="space-y-2">
          <BaseCheckbox v-model="settingsStore.notifications[FtWsMessageTypes.entryFill]">
            {{ t('settings.entryNotifications') }}
          </BaseCheckbox>
          <BaseCheckbox v-model="settingsStore.notifications[FtWsMessageTypes.exitFill]">
            {{ t('settings.exitNotifications') }}
          </BaseCheckbox>
          <BaseCheckbox v-model="settingsStore.notifications[FtWsMessageTypes.entryCancel]">
            {{ t('settings.entryCancelNotifications') }}
          </BaseCheckbox>
          <BaseCheckbox v-model="settingsStore.notifications[FtWsMessageTypes.exitCancel]">
            {{ t('settings.exitCancelNotifications') }}
          </BaseCheckbox>
        </div>
      </div>

      <div class="border rounded-sm border-neutral-400 p-4 space-y-4">
        <h4 class="text-lg font-semibold">{{ t('settings.backtesting') }}</h4>
        <div>
          <label for="backtestMetrics" class="block">{{ t('settings.backtestMetrics') }}</label>
          <USelectMenu
            multiple
            id="backtestMetrics"
            v-model="settingsStore.backtestAdditionalMetrics"
            :items="localizedBacktestMetricOptions"
            label-key="header"
            value-key="field"
            class="w-full"
            display="chip"
          />
          <small class="text-sm text-neutral-600 dark:text-neutral-400">{{
            t('settings.backtestMetricsHint')
          }}</small>
        </div>
      </div>

      <div class="border rounded-sm border-neutral-400 p-4 space-y-4">
        <h4 class="text-lg font-semibold">{{ t('settings.showcase.title') }}</h4>
        <small class="block text-sm text-neutral-600 dark:text-neutral-400">
          {{ t('settings.showcase.hint') }}
        </small>

        <p
          v-if="showcaseRows.length === 0"
          class="text-sm text-neutral-600 dark:text-neutral-400"
        >
          {{ t('settings.showcase.empty') }}
        </p>

        <div
          v-for="row in showcaseRows"
          :key="row.botId"
          class="space-y-3 border border-neutral-300/60 rounded-sm p-3"
        >
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="font-semibold">{{ row.name }}</span>
            <span class="text-xs break-all text-neutral-500 dark:text-neutral-400">
              {{ row.url }}
            </span>
          </div>

          <BaseCheckbox v-model="showcaseEnabled[row.botId]">
            {{ t('settings.showcase.enabled') }}
          </BaseCheckbox>

          <div class="flex flex-wrap items-center gap-3">
            <UInput
              v-model="showcaseLabels[row.botId]"
              :placeholder="row.name"
              class="min-w-40 flex-1"
            />
            <BaseCheckbox v-model="showcaseShowAbsolute[row.botId]">
              {{ t('settings.showcase.showAbsolute') }}
            </BaseCheckbox>
          </div>
          <small class="block text-sm text-neutral-600 dark:text-neutral-400">
            {{ t('settings.showcase.labelHint') }}
          </small>

          <p
            v-if="showcaseStatus[row.botId] === 'unsupported'"
            class="text-sm text-amber-600 dark:text-amber-400"
          >
            {{ t('settings.showcase.unsupported') }}
          </p>
          <p
            v-else-if="showcaseStatus[row.botId] === 'error'"
            class="text-sm text-rose-600 dark:text-rose-400"
          >
            {{ t('settings.showcase.loadError') }}
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <UButton :loading="showcaseSaving" @click="saveShowcaseSettings">
            {{ t('settings.showcase.save') }}
          </UButton>
          <UButton color="neutral" @click="generateShareLink">
            {{ t('settings.showcase.generate') }}
          </UButton>
          <UButton v-if="shareLink" color="neutral" @click="copyShareLink">
            {{ t('settings.showcase.copy') }}
          </UButton>
        </div>

        <div v-if="shareLink" class="space-y-1">
          <label class="block text-sm">{{ t('settings.showcase.shareTitle') }}</label>
          <UInput :model-value="shareLink" readonly class="w-full" />
          <small class="block text-sm text-neutral-600 dark:text-neutral-400">
            {{ t('settings.showcase.shareHint') }}
          </small>
        </div>
      </div>
    </div>
  </UCard>
</template>
