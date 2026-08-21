<script setup lang="ts">
import type { Pairlist } from '@/types';
import { useI18n } from 'vue-i18n';
import { localizePairlistText } from '@/i18n/pairlistText';
import { useSortable, moveArrayElement } from '@vueuse/integrations/useSortable';

const botStore = useBotStore();
const pairlistStore = usePairlistConfigStore();
const { t, locale } = useI18n();

const availablePairlists = ref<Pairlist[]>([]);
const pairlistConfigsEl = ref<HTMLElement | null>(null);
const availablePairlistsEl = ref<HTMLElement | null>(null);
const selectedView = ref<'Config' | 'Results'>('Config');
const viewItems = computed(() => [
  { value: 'Config', label: t('research.configuration') },
  { value: 'Results', label: t('research.results'), disabled: pairlistStore.whitelist.length === 0 },
]);

const configEmpty = computed(() => {
  return pairlistStore.config.pairlists.length == 0;
});

useSortable(availablePairlistsEl, availablePairlists.value, {
  group: {
    name: 'configurator',
    pull: 'clone',
    put: false,
  },
  sort: false,
  filter: '.no-drag',
  dragClass: 'dragging',
});

useSortable(pairlistConfigsEl, pairlistStore.config.pairlists, {
  handle: '.handle',
  group: 'configurator',
  onUpdate: async (e) => {
    if (e.oldIndex === undefined || e.newIndex === undefined) {
      return;
    }
    moveArrayElement(pairlistStore.config.pairlists, e.oldIndex, e.newIndex);
  },
  onAdd: (e) => {
    if (e.oldIndex === undefined || e.newIndex === undefined) {
      return;
    }
    const pairlist = availablePairlists.value[e.oldIndex];
    if (!pairlist) {
      console.error('Pairlist not found');
      return;
    }
    pairlistStore.addToConfig(pairlist, e.newIndex);
    // quick fix from: https://github.com/SortableJS/Sortable/issues/1515
    e.clone.replaceWith(e.item);
    e.clone.remove();
  },
});

onMounted(async () => {
  availablePairlists.value = (await botStore.activeBot.getPairlists()).pairlists.sort((a, b) =>
    // Sort by is_pairlist_generator (by name), then by name.
    // TODO: this might need to be improved
    a.is_pairlist_generator === b.is_pairlist_generator
      ? a.name.localeCompare(b.name)
      : a.is_pairlist_generator
        ? -1
        : 1,
  );
  pairlistStore.selectOrCreateConfig(
    pairlistStore.isSavedConfig(pairlistStore.configName) ? pairlistStore.configName : 'default',
  );
});

watch(
  () => pairlistStore.whitelist,
  () => {
    selectedView.value = 'Results';
  },
);

if (pairlistStore.whitelist.length > 0) {
  selectedView.value = 'Results';
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-[auto_1fr_auto] px-3 mb-3 gap-3 w-full">
    <ul
      ref="availablePairlistsEl"
      class="divide-y border-x border-neutral-500 rounded-sm border-y divide-solid divide-neutral-500 min-w-72"
    >
      <li class="px-3 py-2 font-bold bg-neutral-100 dark:bg-neutral-800">
        {{ t('research.availablePairlists') }}
      </li>
      <!-- Available pairlists-->
      <li
        v-for="pairlist in availablePairlists"
        :key="pairlist.name"
        :class="{
          'no-drag text-gray-500 hover:cursor-default':
            pairlistStore.config.pairlists.length === 0 && !pairlist.is_pairlist_generator,
        }"
        class="flex text-start items-center py-2 px-3 hover:cursor-grab [.dragging]:bg-neutral-100 dark:[.dragging]:bg-neutral-900 [.dragging]:border [.dragging]:border-neutral-500"
      >
        <div class="flex grow items-start flex-col">
          <span class="font-bold">{{ pairlist.name }}</span>
          <span class="text-sm text-muted">{{ localizePairlistText(pairlist.description, locale) }}</span>
        </div>
        <UButton
          color="neutral"
          variant="ghost"
          :disabled="pairlistStore.config.pairlists.length === 0 && !pairlist.is_pairlist_generator"
          icon="mdi:arrow-right-bold-box-outline"
          @click="pairlistStore.addToConfig(pairlist, pairlistStore.config.pairlists.length)"
        />
      </li>
    </ul>
    <div class="flex flex-col">
      <PairlistConfigActions />
      <div class="border rounded-sm border-neutral-500 p-2 mb-2">
        <div class="flex items-center gap-2 my-2">
          <span class="col-auto">{{ t('research.stakeCurrency') }}: </span>
          <UInput v-model="pairlistStore.stakeCurrency" />
        </div>

        <div class="mb-2 border rounded-sm border-neutral-500 p-2 text-start">
          <BaseCheckbox v-model="pairlistStore.customExchange" class="mb-2">
            {{ t('research.customExchange') }}
          </BaseCheckbox>
          <Transition name="fade">
            <ExchangeSelect
              v-if="pairlistStore.customExchange"
              v-model="pairlistStore.selectedExchange"
            />
          </Transition>
        </div>
      </div>
      <PairlistConfigBlacklist />
      <UAlert
        v-if="pairlistStore.config.pairlists.length > 0 && !pairlistStore.firstPairlistIsGenerator"
        class="my-2"
        color="warning"
        :title="t('research.invalidConfiguration')"
        :description="t('research.pairlistGeneratorRequired')"
      />
      <div
        ref="pairlistConfigsEl"
        class="flex flex-col grow relative border rounded-sm border-neutral-500 p-1 gap-2 min-h-32"
        :class="{ empty: configEmpty }"
      >
        <div
          v-if="configEmpty"
          class="absolute inset-0 flex items-center justify-center text-sm uppercase text-neutral-500 pointer-events-none"
        >
          {{ t('research.dragPairlistHere') }}
        </div>
        <PairlistConfigItem
          v-for="(pairlist, i) in pairlistStore.config.pairlists"
          :key="pairlist.id"
          v-model="pairlistStore.config.pairlists[i]!"
          :index="i"
          @remove="pairlistStore.removeFromConfig"
        />
      </div>
    </div>
    <div class="flex flex-col w-full min-w-72">
      <USegmentedControl
        v-model="selectedView"
        class="mb-2"
        label-key="label"
        value-key="value"
        size="md"
        :items="viewItems"
        disabled-key="disabled"
      >
      </USegmentedControl>
      <div class="relative overflow-auto">
        <CopyableTextfield
          v-if="selectedView === 'Config'"
          class="w-full"
          :content="pairlistStore.configJSON"
          :is-valid="pairlistStore.pairlistValid"
        />
        <CopyableTextfield
          v-if="selectedView === 'Results'"
          class="w-full"
          :content="pairlistStore.whitelist"
        />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
</style>
