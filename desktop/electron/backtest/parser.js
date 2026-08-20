const fs = require('fs');
const path = require('path');
const { readLargestResultJson } = require('./zip');
const { finite, mean, bootstrapMeanCi, evaluate } = require('./eval');

function readResultFile(filename) {
  return path.extname(filename).toLowerCase() === '.zip'
    ? readLargestResultJson(filename)
    : JSON.parse(fs.readFileSync(filename, 'utf8'));
}

function selectStrategy(raw, requested) {
  if (!raw?.strategy || typeof raw.strategy !== 'object') throw new Error('回测结果缺少 strategy 字段');
  if (requested && raw.strategy[requested]) return [requested, raw.strategy[requested]];
  const names = Object.keys(raw.strategy);
  if (names.length !== 1) throw new Error(`回测结果包含多个策略，请指定其中一个：${names.join(', ')}`);
  return [names[0], raw.strategy[names[0]]];
}

function concentration(groups) {
  const positive = [...groups.values()].filter((value) => value > 0);
  const total = positive.reduce((sum, value) => sum + value, 0);
  return total > 0 ? Math.max(0, ...positive) / total : 1;
}

function fallbackDrawdown(values) {
  let equity = 1;
  let peak = 1;
  let maximum = 0;
  for (const value of values) {
    equity += value;
    peak = Math.max(peak, equity);
    maximum = Math.max(maximum, (peak - equity) / Math.max(peak, Number.EPSILON));
  }
  return maximum;
}

function parseResult(raw, options = {}) {
  const [strategy, block] = selectStrategy(raw, options.strategy);
  const slippage = Math.max(0, finite(options.slippage, 0.0005));
  const trades = (block.trades || []).map((trade) => {
    const rawRatio = finite(trade.profit_ratio ?? trade.close_profit);
    return { ...trade, adjustedProfitRatio: rawRatio - (2 * slippage) };
  }).sort((a, b) => String(a.close_date || a.close_date_utc).localeCompare(String(b.close_date || b.close_date_utc)));
  const ratios = trades.map((trade) => trade.adjustedProfitRatio);
  const gains = ratios.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const losses = Math.abs(ratios.filter((value) => value < 0).reduce((sum, value) => sum + value, 0));
  const pairTotals = new Map();
  const monthTotals = new Map();
  const exitTotals = new Map();
  for (const trade of trades) {
    const pair = trade.pair || 'UNKNOWN';
    const month = String(trade.close_date || trade.close_date_utc || '').slice(0, 7) || 'UNKNOWN';
    const reason = trade.exit_reason || 'unknown';
    pairTotals.set(pair, (pairTotals.get(pair) || 0) + trade.adjustedProfitRatio);
    monthTotals.set(month, (monthTotals.get(month) || 0) + trade.adjustedProfitRatio);
    const exit = exitTotals.get(reason) || { reason, trades: 0, profit: 0 };
    exit.trades += 1; exit.profit += trade.adjustedProfitRatio; exitTotals.set(reason, exit);
  }
  const evCi95 = bootstrapMeanCi(ratios, options.bootstrapSamples || 1000);
  const annualReturn = finite(block.cagr, finite(block.profit_total) * (365 / Math.max(1, finite(block.backtest_days, 365))));
  const maxDrawdown = finite(block.max_drawdown_account, fallbackDrawdown(ratios));
  const result = {
    jobId: options.jobId || null,
    strategy,
    timerange: block.timerange || options.timerange || '',
    timeframe: block.timeframe || options.timeframe || '15m',
    backtestDays: finite(block.backtest_days),
    trades: trades.length,
    winRate: trades.length ? ratios.filter((value) => value > 0).length / trades.length : 0,
    profitFactor: losses > 0 ? gains / losses : (gains > 0 ? Number.POSITIVE_INFINITY : 0),
    expectedValue: mean(ratios),
    evCi95,
    annualReturn,
    marketChange: finite(block.market_change, NaN),
    totalProfitRatio: ratios.reduce((sum, value) => sum + value, 0),
    totalProfitAbs: finite(block.profit_total_abs) - trades.reduce((sum, trade) => sum + finite(trade.stake_amount) * 2 * slippage, 0),
    maxDrawdown,
    sharpe: finite(block.sharpe),
    calmar: finite(block.calmar),
    topPairShare: concentration(pairTotals),
    topMonthShare: concentration(monthTotals),
    pairs: [...pairTotals].map(([pair, profit]) => ({ pair, profit, trades: trades.filter((trade) => trade.pair === pair).length })).sort((a, b) => b.profit - a.profit),
    months: [...monthTotals].map(([month, profit]) => ({ month, profit })).sort((a, b) => a.month.localeCompare(b.month)),
    exitReasons: [...exitTotals.values()].sort((a, b) => b.trades - a.trades),
    fees: finite(options.fee, 0.0004),
    slippage,
    assumptions: [
      `手续费 ${(finite(options.fee, 0.0004) * 100).toFixed(3)}%（传入 Freqtrade）`,
      `每次进出场各扣除滑点 ${(slippage * 100).toFixed(3)}%（解析后压力调整）`,
      '未计永续合约资金费率',
      '结果仅代表指定历史样本，不保证未来收益',
    ],
    notes: [],
  };
  const automaticEvidence = Number.isFinite(result.marketChange) && result.backtestDays > 0
    ? { buyHoldAnnualReturn: Math.pow(Math.max(0.000001, 1 + result.marketChange), 365 / result.backtestDays) - 1 }
    : {};
  result.evalResult = evaluate(result, { ...automaticEvidence, ...(options.evidence || {}) });
  return result;
}

function parseResultFile(filename, options = {}) {
  return parseResult(readResultFile(filename), options);
}

module.exports = { readResultFile, selectStrategy, parseResult, parseResultFile, concentration, fallbackDrawdown };
