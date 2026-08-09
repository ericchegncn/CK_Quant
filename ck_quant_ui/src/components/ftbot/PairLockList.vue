<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { Lock } from '@/types';
import type { TableColumn } from '@nuxt/ui';

const botStore = useBotStore();
const { t } = useI18n();

const columns = computed<TableColumn<Lock>[]>(() => [
  { accessorKey: 'pair', header: t('workspace.pair') },
  { accessorKey: 'lock_end_timestamp', header: t('workspace.until') },
  { accessorKey: 'reason', header: t('workspace.reason') },
  { id: 'actions', header: t('workspace.actions') },
]);

function removePairLock(item: Lock) {
  console.log(item);
  if (item.id !== undefined) {
    botStore.activeBot.deleteLock(item.id);
  } else {
    showAlert(t('workspace.lockDeleteUnsupported'));
  }
}
</script>

<template>
  <div>
    <div class="mb-2">
      <label class="me-auto text-xl">{{ t('workspace.pairLocks') }}</label>
      <UButton
        class="float-end"
        color="neutral"
        icon="mdi:refresh"
        @click="botStore.activeBot.getLocks"
      />
    </div>
    <UTable
      :data="botStore.activeBot.activeLocks"
      :columns="columns"
      :ui="{
        td: 'whitespace-normal',
      }"
    >
      <template #lock_end_timestamp-cell="{ row }">
        {{ timestampms(row.original.lock_end_timestamp) }}
      </template>
      <template #actions-cell="{ row }">
        <UButton
          class="btn-xs ms-1"
          size="sm"
          color="neutral"
          :title="t('workspace.deleteLock')"
          icon="mdi:delete"
          @click="removePairLock(row.original)"
        />
      </template>
    </UTable>
  </div>
</template>
