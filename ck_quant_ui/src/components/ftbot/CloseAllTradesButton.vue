<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import type { Trade } from '@/types';

const props = withDefaults(
  defineProps<{
    /** 当前列表里展示的持仓（决定了按钮的作用范围与数量） */
    trades: Trade[];
    /** 紧凑模式（手机端） */
    compact?: boolean;
  }>(),
  {
    compact: false,
  },
);

const { t } = useI18n();
const botStore = useBotStore();
const { confirm } = useConfirmBox();

const busy = ref(false);

const openCount = computed(() => props.trades.filter((trade) => trade.is_open).length);

/**
 * 只作用于「当前列表里出现的那些 bot」。
 * 若列表是多 bot 合并视图，就平掉这些 bot；避免出现
 * 「界面显示 33 笔、按钮只平掉当前那一个 bot 的 12 笔」这种更危险的意外。
 */
const targetBotIds = computed(() => {
  const ids = props.trades
    .map((trade) => (trade as Trade & { botId?: string }).botId)
    .filter((value): value is string => typeof value === 'string' && value.length > 0);
  const unique = [...new Set(ids)];
  return unique.length > 0 ? unique : [botStore.selectedBot].filter((v) => v.length > 0);
});

/** 目标 bot 里是否有实盘（实盘要多一次确认） */
const includesLive = computed(() =>
  targetBotIds.value.some((botId) => {
    const store = botStore.allBotStores.find((bot) => bot.botId === botId);
    return store?.botState?.runmode === 'live';
  }),
);

async function closeAllTrades() {
  const n = openCount.value;
  if (n === 0 || busy.value) return;

  // 注意：这里刻意不受「跳过确认弹窗」设置影响 —— 不可逆的批量操作必须确认。
  const confirmed = await confirm({
    title: t('workspace.closeAllTrades'),
    description: t('workspace.irreversible'),
    message: t('workspace.confirmCloseAllTrades', { n }),
    confirmText: t('workspace.confirm'),
  });
  if (!confirmed) return;

  if (includesLive.value) {
    const confirmedLive = await confirm({
      title: t('workspace.closeAllTrades'),
      description: t('workspace.irreversible'),
      message: t('workspace.confirmCloseAllTradesLive', { n }),
      confirmText: t('workspace.confirm'),
    });
    if (!confirmedLive) return;
  }

  busy.value = true;
  try {
    // tradeid: 'all' 由后端 rpc._rpc_force_exit 展开为「所有未平仓」，逐笔平仓。
    await Promise.all(
      targetBotIds.value.map((botId) =>
        botStore
          .forceSellMulti({ tradeid: 'all', botId })
          .catch((error) => console.log(error?.response ?? error)),
      ),
    );
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <UButton
    v-if="openCount > 0"
    color="neutral"
    variant="outline"
    size="sm"
    icon="mdi:close-box-multiple"
    :loading="busy"
    :title="t('workspace.closeAllTradesHint')"
    :label="
      compact
        ? t('workspace.closeAllTrades')
        : `${t('workspace.closeAllTrades')} (${openCount})`
    "
    @click="closeAllTrades"
  />
</template>
