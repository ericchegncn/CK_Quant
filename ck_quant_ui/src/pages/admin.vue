<script setup lang="ts">
import type {
  AdminBackupInfo,
  AdminCapabilities,
  AdminDocumentKind,
  AdminMarketsResponse,
  EditableAdminDocument,
} from '@/types';
import { RunModes } from '@/types';
<<<<<<< HEAD
import { normalizeAdminConfigSource } from '@/utils/adminConfig';
=======
import { applyManualPairWhitelist, normalizeAdminConfigSource } from '@/utils/adminConfig';
>>>>>>> origin/main
import axios from 'axios';
import { useI18n } from 'vue-i18n';

const botStore = useBotStore();
const { confirm } = useConfirmBox();
const { t } = useI18n();

const capabilities = ref<AdminCapabilities>();
const documentKind = ref<AdminDocumentKind>('config');
const document = ref<EditableAdminDocument>();
const source = ref('');
const loading = ref(true);
const saving = ref(false);
const unavailable = ref(false);
const backupId = ref('');
const backups = ref<AdminBackupInfo[]>([]);
const marketData = ref<AdminMarketsResponse>();
const marketsLoading = ref(false);
const marketsError = ref('');

const canEdit = computed(() =>
  documentKind.value === 'config'
    ? capabilities.value?.config_edit
    : capabilities.value?.strategy_edit,
);

const tabs = computed(() => [
  { label: t('admin.config'), value: 'config', icon: 'mdi:file-cog-outline' },
  { label: t('admin.strategy'), value: 'strategy', icon: 'mdi:code-braces' },
]);
const visibleBackups = computed(() =>
  backups.value.filter((backup) => backup.kind === documentKind.value).slice(0, 10),
);

const configModel = computed<Record<string, unknown> | undefined>(() => {
  if (documentKind.value !== 'config') return undefined;
  try {
    return JSON.parse(source.value) as Record<string, unknown>;
  } catch {
    return undefined;
  }
});

function updateConfig(key: string, value: unknown) {
  if (!configModel.value) return;
  source.value = JSON.stringify({ ...configModel.value, [key]: value }, null, 2);
}

const maxOpenTrades = computed({
  get: () => Number(configModel.value?.max_open_trades ?? 0),
  set: (value: number) => updateConfig('max_open_trades', value),
});
const stakeAmount = computed({
  get: () => String(configModel.value?.stake_amount ?? ''),
  set: (value: string) => updateConfig('stake_amount', value),
});
const timeframe = computed({
  get: () => String(configModel.value?.timeframe ?? ''),
  set: (value: string) => updateConfig('timeframe', value),
});
const strategyName = computed({
  get: () => String(configModel.value?.strategy ?? ''),
  set: (value: string) => updateConfig('strategy', value),
});
const dryRun = computed({
  get: () => Boolean(configModel.value?.dry_run),
  set: (value: boolean) => updateConfig('dry_run', value),
});
const pairWhitelist = computed({
  get: () => {
    const exchange = configModel.value?.exchange as Record<string, unknown> | undefined;
    return Array.isArray(exchange?.pair_whitelist) ? exchange.pair_whitelist.join('\n') : '';
  },
  set: (value: string) => {
    if (!configModel.value) return;
<<<<<<< HEAD
    const exchange = (configModel.value.exchange as Record<string, unknown> | undefined) ?? {};
    source.value = JSON.stringify(
      {
        ...configModel.value,
        exchange: {
          ...exchange,
          pair_whitelist: value
            .split('\n')
            .map((pair) => pair.trim())
            .filter(Boolean),
        },
      },
      null,
      2,
    );
=======
    const whitelist = value
      .split('\n')
      .map((pair) => pair.trim())
      .filter(Boolean);
    source.value = JSON.stringify(applyManualPairWhitelist(configModel.value, whitelist), null, 2);
>>>>>>> origin/main
  },
});

const pairWhitelistEntries = computed({
  get: () => {
    const exchange = configModel.value?.exchange as Record<string, unknown> | undefined;
    return Array.isArray(exchange?.pair_whitelist)
      ? exchange.pair_whitelist.filter((pair): pair is string => typeof pair === 'string')
      : [];
  },
  set: (value: string[]) => {
    pairWhitelist.value = value.join('\n');
  },
});

function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 409) return t('admin.conflict');
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return t('admin.actionFailed');
}

async function loadDocument() {
  loading.value = true;
  try {
    const result = await botStore.activeBot.getAdminDocument(documentKind.value);
    document.value = result;
    source.value = result.source;
    backupId.value = '';
  } catch (error) {
    showAlert(errorMessage(error), 'error');
  } finally {
    loading.value = false;
  }
}

async function loadAdmin() {
  loading.value = true;
  try {
    capabilities.value = await botStore.activeBot.getAdminCapabilities();
    unavailable.value = !capabilities.value.enabled;
    if (!unavailable.value) {
      await Promise.all([loadDocument(), loadBackups(), loadMarkets()]);
    }
  } catch (error) {
    unavailable.value = true;
    if (!axios.isAxiosError(error) || error.response?.status !== 404) {
      showAlert(t('admin.loadFailed'), 'error');
    }
  } finally {
    loading.value = false;
  }
}

async function loadBackups() {
  try {
    backups.value = await botStore.activeBot.getAdminBackups();
  } catch (error) {
    showAlert(errorMessage(error), 'error');
  }
}

async function loadMarkets() {
  marketsLoading.value = true;
  marketsError.value = '';
  try {
    marketData.value = await botStore.activeBot.getAdminMarkets();
  } catch {
    marketsError.value = t('admin.marketLoadFailed');
  } finally {
    marketsLoading.value = false;
  }
}

async function validateDocument() {
  try {
    const sourceToValidate =
      documentKind.value === 'config' ? normalizeAdminConfigSource(source.value) : source.value;
    await botStore.activeBot.validateAdminDocument(documentKind.value, sourceToValidate);
    source.value = sourceToValidate;
    showAlert(t('admin.valid'), 'success');
    return true;
  } catch (error) {
    showAlert(errorMessage(error), 'error');
    return false;
  }
}

async function saveDocument(apply: boolean) {
  if (!document.value || !canEdit.value || saving.value) return;
  if (!(await validateDocument())) return;

  if (apply) {
    const isLive = botStore.activeBot.botState?.runmode === RunModes.LIVE;
    const accepted = await confirm({
      title: t('admin.confirmTitle'),
      message: isLive ? t('admin.liveConfirmMessage') : t('admin.confirmMessage'),
      cancelText: t('common.cancel'),
      confirmText: t('admin.saveApply'),
    });
    if (!accepted) return;
  }

  saving.value = true;
  try {
    const result = await botStore.activeBot.saveAdminDocument(documentKind.value, {
      source: source.value,
      revision: document.value.revision,
      apply,
    });
    backupId.value = result.backup_id;
    showAlert(apply ? t('admin.applying') : t('admin.saved'), 'success');
    await loadDocument();
    await loadBackups();
    backupId.value = result.backup_id;
  } catch (error) {
    showAlert(errorMessage(error), 'error');
  } finally {
    saving.value = false;
  }
}

async function restoreBackup(backup: AdminBackupInfo) {
  if (!document.value || saving.value) return;
  const accepted = await confirm({
    title: t('admin.restore'),
    message: t('admin.restoreConfirm'),
    cancelText: t('common.cancel'),
    confirmText: t('admin.restore'),
  });
  if (!accepted) return;
  saving.value = true;
  try {
    await botStore.activeBot.restoreAdminBackup(documentKind.value, {
      backup_id: backup.backup_id,
      revision: document.value.revision,
      apply: true,
    });
    showAlert(t('admin.restoreSuccess'), 'success');
    await Promise.all([loadDocument(), loadBackups()]);
  } catch (error) {
    showAlert(errorMessage(error), 'error');
  } finally {
    saving.value = false;
  }
}

watch(documentKind, loadDocument);
onMounted(loadAdmin);
</script>

<template>
  <div class="mx-auto flex w-full max-w-7xl flex-col gap-5 p-4 md:p-6">
    <div>
      <h1 class="text-2xl font-bold">{{ t('admin.title') }}</h1>
      <p class="text-muted mt-1">{{ t('admin.description') }}</p>
    </div>

    <UAlert
      v-if="unavailable"
      color="warning"
      icon="mdi:shield-lock-outline"
      :title="t('admin.unavailableTitle')"
      :description="t('admin.unavailableDescription')"
    />

    <template v-else>
      <UTabs v-model="documentKind" :items="tabs" class="w-full" />

      <div v-if="loading" class="flex min-h-64 items-center justify-center">
        <UIcon name="mdi:loading" class="size-8 animate-spin" />
      </div>

      <template v-else-if="document">
        <UCard v-if="documentKind === 'config' && configModel">
          <template #header>
            <h2 class="font-semibold">{{ t('admin.quickSettings') }}</h2>
          </template>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <UFormField :label="t('admin.maxOpenTrades')">
              <UInputNumber v-model="maxOpenTrades" class="w-full" :min="-1" />
            </UFormField>
            <UFormField :label="t('admin.stakeAmount')">
              <UInput v-model="stakeAmount" class="w-full" />
            </UFormField>
            <UFormField :label="t('admin.timeframe')">
              <UInput v-model="timeframe" class="w-full" />
            </UFormField>
            <UFormField :label="t('admin.strategyName')">
              <UInput v-model="strategyName" class="w-full" />
            </UFormField>
            <UFormField :label="t('admin.dryRun')">
              <USwitch v-model="dryRun" />
            </UFormField>
            <UFormField :label="t('admin.pairWhitelist')" :hint="t('admin.pairWhitelistHint')">
              <UTextarea v-model="pairWhitelist" class="w-full" :rows="5" />
            </UFormField>
          </div>
        </UCard>

        <PairWhitelistManager
          v-if="documentKind === 'config' && configModel"
          v-model:whitelist="pairWhitelistEntries"
          :market-data="marketData"
          :loading="marketsLoading"
          :error="marketsError"
          :disabled="!canEdit"
          @refresh="loadMarkets"
        />

        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h2 class="font-semibold">{{ t('admin.advancedEditor') }}</h2>
              <UButton
                color="neutral"
                variant="outline"
                icon="mdi:refresh"
                :label="t('admin.reload')"
                @click="loadDocument"
              />
            </div>
          </template>

          <UAlert
            color="warning"
            variant="subtle"
            icon="mdi:alert-outline"
            :description="t('admin.sourceWarning')"
            class="mb-3"
          />
          <p v-if="document.redacted" class="text-muted mb-3 text-sm">
            {{ t('admin.redactedHint') }}
          </p>
          <UTextarea
            v-model="source"
            :disabled="!canEdit"
            :rows="documentKind === 'strategy' ? 28 : 22"
            class="admin-editor w-full"
            autoresize
            spellcheck="false"
          />

          <div class="text-muted mt-3 grid gap-1 text-xs md:grid-cols-3">
            <span>{{ t('admin.file') }}: {{ document.name }}</span>
            <span>{{ t('admin.updated') }}: {{ document.updated_at }}</span>
            <span v-if="backupId">{{ t('admin.backup') }}: {{ backupId }}</span>
          </div>

          <template #footer>
            <div class="flex flex-wrap justify-end gap-2">
              <UButton
                color="neutral"
                variant="outline"
                icon="mdi:check-decagram-outline"
                :label="t('admin.validate')"
                :disabled="!canEdit"
                @click="validateDocument"
              />
              <UButton
                color="neutral"
                icon="mdi:content-save-outline"
                :label="t('admin.save')"
                :loading="saving"
                :disabled="!canEdit"
                @click="saveDocument(false)"
              />
              <UButton
                icon="mdi:restart"
                :label="t('admin.saveApply')"
                :loading="saving"
                :disabled="!canEdit || !capabilities?.apply_reload"
                @click="saveDocument(true)"
              />
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <h2 class="font-semibold">{{ t('admin.backupHistory') }}</h2>
          </template>
          <p v-if="visibleBackups.length === 0" class="text-muted text-sm">
            {{ t('admin.noBackups') }}
          </p>
          <div v-else class="divide-default divide-y">
            <div
              v-for="backup in visibleBackups"
              :key="backup.backup_id"
              class="flex flex-col justify-between gap-2 py-3 sm:flex-row sm:items-center"
            >
              <div class="min-w-0">
                <p class="truncate font-mono text-xs">{{ backup.backup_id }}</p>
                <p class="text-muted text-xs">
                  {{ new Date(backup.created_at).toLocaleString() }} ·
                  {{ Math.ceil(backup.size / 1024) }} KB
                </p>
              </div>
              <UButton
                color="warning"
                variant="outline"
                icon="mdi:backup-restore"
                :label="t('admin.restore')"
                :loading="saving"
                @click="restoreBackup(backup)"
              />
            </div>
          </div>
        </UCard>
      </template>
    </template>
  </div>
</template>

<style scoped>
:deep(.admin-editor textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.45;
  tab-size: 4;
}
</style>
