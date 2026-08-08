<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { ForceEnterPayload } from '@/types';
import { OrderSides } from '@/types';

export interface ForceEntryFormProps {
  pair?: string;
  positionIncrease?: boolean;
}

const props = withDefaults(defineProps<ForceEntryFormProps>(), {
  pair: '',
  positionIncrease: false,
});

const emit = defineEmits<{
  close: [value: boolean];
}>();

const botStore = useBotStore();
const { t } = useI18n();

const form = ref<HTMLFormElement>();
const selectedPair = ref('');
const price = ref<number | undefined>(undefined);
const stakeAmount = ref<number | undefined>(undefined);
const leverage = ref<number | undefined>(undefined);

const ordertype = ref('');
const orderSide = ref<OrderSides>(OrderSides.long);
const enterTag = ref('force_entry');

const orderTypeOptions = computed(() => [
  { value: 'market', text: t('workspace.market') },
  { value: 'limit', text: t('workspace.limit') },
]);
const orderSideOptions = computed(() => [
  { value: 'long', text: t('workspace.long') },
  { value: 'short', text: t('workspace.short') },
]);

function checkFormValidity() {
  const valid = form.value?.checkValidity();

  return valid;
}

async function handleEntry() {
  // Exit when the form isn't valid
  if (!checkFormValidity()) {
    return;
  }

  // call forceentry
  const payload: ForceEnterPayload = { pair: selectedPair.value };
  if (price.value) {
    payload.price = Number(price.value);
  }
  if (ordertype.value) {
    payload.ordertype = ordertype.value;
  }
  if (stakeAmount.value) {
    payload.stakeamount = stakeAmount.value;
  }
  if (botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed) {
    payload.side = orderSide.value;
  }
  if (botStore.activeBot.botFeatures.forceEntryTag && enterTag.value) {
    payload.entry_tag = enterTag.value;
  }

  if (leverage.value) {
    payload.leverage = leverage.value;
  }
  botStore.activeBot.forceentry(payload);
  emit('close', true);
}

function resetForm() {
  selectedPair.value = props.pair;
  price.value = undefined;
  stakeAmount.value = undefined;
  ordertype.value =
    botStore.activeBot.botState?.order_types?.forcebuy ||
    botStore.activeBot.botState?.order_types?.force_entry ||
    botStore.activeBot.botState?.order_types?.buy ||
    botStore.activeBot.botState?.order_types?.entry ||
    'limit';
}

resetForm();
</script>

<template>
  <UModal
    :title="
      positionIncrease
        ? t('workspace.increasingPositionFor', { pair })
        : t('workspace.forceEnteringTrade')
    "
    :description="
      positionIncrease ? t('workspace.increaseExistingPosition') : t('workspace.manuallyEnterTrade')
    "
  >
    <template #body>
      <form ref="form" class="space-y-4" @submit.prevent="handleEntry">
        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed"
          :label="t('workspace.orderDirection')"
        >
          <USegmentedControl
            v-model="orderSide"
            :items="orderSideOptions"
            label-key="text"
            value-key="value"
            size="sm"
            class="w-full"
          />
        </UFormField>

        <UFormField :label="t('workspace.pair')" required>
          <UInput
            v-model="selectedPair"
            :disabled="positionIncrease"
            required
            class="w-full"
            @keydown.enter="handleEntry"
            @focus="($event.target as HTMLInputElement).select()"
          />
        </UFormField>

        <UFormField :label="t('workspace.priceOptional')">
          <UInputNumber
            v-model="price"
            show-buttons
            :min="0"
            :stepSnapping="false"
            :format-options="{
              maximumFractionDigits: 8,
            }"
            :step="0.1"
            class="w-full"
            @keydown.enter="handleEntry"
          />
        </UFormField>

        <UFormField
          :label="
            t('workspace.stakeAmountOptional', { currency: botStore.activeBot.stakeCurrency })
          "
        >
          <UInputNumber
            v-model="stakeAmount"
            show-buttons
            :min="0"
            :stepSnapping="false"
            :step="['USDC', 'USDT'].includes(botStore.activeBot.stakeCurrency) ? 10 : 1"
            class="w-full"
            :format-options="{
              maximumFractionDigits: 5,
            }"
          />
        </UFormField>

        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed"
          :label="t('workspace.leverageOptional')"
        >
          <UInputNumber
            id="leverage-input"
            v-model="leverage"
            show-buttons
            :min="1"
            :step="1"
            :max-fraction-digits="1"
            class="w-full"
            @keydown.enter="handleEntry"
          />
        </UFormField>

        <UFormField :label="t('workspace.orderType')">
          <USegmentedControl
            v-model="ordertype"
            :items="orderTypeOptions"
            label-key="text"
            value-key="value"
            size="sm"
            class="w-full"
          />
        </UFormField>

        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEntryTag"
          :label="t('workspace.customEntryTagOptional')"
        >
          <UInput id="enterTag-input" v-model="enterTag" class="w-full" />
        </UFormField>
      </form>
    </template>
    <template #footer>
      <div class="ms-auto flex justify-end gap-2">
        <UButton color="neutral" @click="$emit('close', false)" icon="mdi:close">{{
          t('workspace.cancel')
        }}</UButton>
        <UButton @click="handleEntry" icon="mdi:check">{{ t('workspace.enterPosition') }}</UButton>
      </div>
    </template>
  </UModal>
</template>
