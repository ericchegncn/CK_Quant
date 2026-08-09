<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const botStore = useBotStore();
const { t } = useI18n();
</script>

<template>
  <div v-if="botStore.activeBot.botState" class="p-4">
    <p class="mb-4">
      {{ t('workspace.runningVersion', { version: botStore.activeBot.version }) }}
    </p>
    <p class="mb-4">
      {{
        t('workspace.runningWith', {
          maxTrades: botStore.activeBot.botState.max_open_trades,
          stake: botStore.activeBot.botState.stake_amount,
          currency: botStore.activeBot.botState.stake_currency,
        })
      }}
      {{
        t('workspace.onExchange', {
          exchange: `${botStore.activeBot.botState.exchange}${
            botStore.activeBot.botState.demo_trading ? ` (${t('workspace.demo')})` : ''
          }`,
        })
      }}
      {{
        t('workspace.inMarketsWithStrategy', {
          mode: `${botStore.activeBot.botState.trading_mode || 'spot'} ${
            botStore.activeBot.botState.trading_mode !== 'spot'
              ? (botStore.activeBot.botState.margin_mode ?? '')
              : ''
          }`.trim(),
          strategy: botStore.activeBot.botState.strategy,
        })
      }}
    </p>
    <p v-if="'stoploss_on_exchange' in botStore.activeBot.botState" class="mb-4">
      {{
        t('workspace.stoplossOnExchange', {
          status: botStore.activeBot.botState.stoploss_on_exchange
            ? t('workspace.enabled')
            : t('workspace.disabled'),
        })
      }}
    </p>
    <p class="mb-4">
      {{
        t('workspace.currentState', {
          state: botStore.activeBot.botState.state,
          forceEntry: botStore.activeBot.botState.force_entry_enable,
        })
      }}
    </p>
    <p>
      <strong>{{
        botStore.activeBot.botState.dry_run ? t('workspace.dryRunMode') : t('workspace.liveMode')
      }}</strong>
    </p>
    <USeparator class="my-2" />
    <p class="mb-4" v-if="botStore.activeBot.profit">
      {{
        t('workspace.averageProfit', {
          average: formatPercent(botStore.activeBot.profit.profit_all_ratio_mean),
          total: formatPercent(botStore.activeBot.profit.profit_all_ratio_sum),
          count: botStore.activeBot.profit.trade_count,
          duration: botStore.activeBot.profit.avg_duration,
          pair: botStore.activeBot.profit.best_pair,
        })
      }}
    </p>
    <p v-if="botStore.activeBot.profit?.first_trade_timestamp" class="mb-4">
      <span v-if="botStore.activeBot.profit.bot_start_timestamp" class="block">
        {{ t('workspace.botStartDate') }}:
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.bot_start_timestamp" show-timezone />
        </strong>
      </span>
      <span class="block">
        {{ t('workspace.firstTradeOpened') }}:
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.first_trade_timestamp" show-timezone />
        </strong>
      </span>
      <span class="block">
        {{ t('workspace.lastTradeOpened') }}:
        <strong>
          <DateTimeTZ :date="botStore.activeBot.profit.latest_trade_timestamp" show-timezone />
        </strong>
      </span>
    </p>
    <p>
      <span v-if="botStore.activeBot.profit?.profit_factor" class="block">
        {{ t('workspace.profitFactor') }}:
        {{ formatNumber(botStore.activeBot.profit?.profit_factor, 2) }}
      </span>
      <span v-if="botStore.activeBot.profit?.trading_volume" class="block mb-4">
        {{ t('workspace.tradingVolume') }}:
        {{
          formatPriceCurrency(
            botStore.activeBot.profit.trading_volume,
            botStore.activeBot.botState.stake_currency,
            botStore.activeBot.botState.stake_currency_decimals ?? 3,
          )
        }}
      </span>
    </p>
    <BaseCollapsible
      v-if="botStore.activeBot.strategy?.params"
      :title="t('workspace.strategyParameters')"
    >
      <StrategyParameters :strategy="botStore.activeBot.strategy" class="m-3" />
    </BaseCollapsible>
    <USeparator class="my-5" />
    <BotProfit
      class="mx-1"
      v-if="botStore.activeBot.profitAll"
      :profit-all="botStore.activeBot.profitAll"
      :stake-currency="botStore.activeBot.botState.stake_currency ?? 'USDT'"
      :stake-currency-decimals="botStore.activeBot.botState.stake_currency_decimals ?? 3"
    />
  </div>
</template>
