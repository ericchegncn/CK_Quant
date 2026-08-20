const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { parseResult } = require('../electron/backtest/parser');
const { evaluate } = require('../electron/backtest/eval');
const { BacktestService, validateSubmit } = require('../electron/backtest/service');

function fixture(strategy = 'TestStrategy', count = 400) {
  const trades = Array.from({ length: count }, (_, index) => ({
    pair: index % 3 === 0 ? 'BTC/USDT:USDT' : index % 3 === 1 ? 'ETH/USDT:USDT' : 'SOL/USDT:USDT',
    close_date: `2025-${String((index % 12) + 1).padStart(2, '0')}-15 00:00:00`,
    profit_ratio: index % 3 === 0 ? -0.004 : 0.006,
    profit_abs: index % 3 === 0 ? -0.4 : 0.6,
    stake_amount: 100,
    exit_reason: index % 3 === 0 ? 'stop_loss' : 'custom_exit',
  }));
  return { strategy: { [strategy]: { trades, timeframe: '15m', timerange: '20240101-20260101', backtest_days: 731, cagr: 0.2, max_drawdown_account: 0.12, profit_total_abs: 80, sharpe: 1.2, calmar: 1.6 } } };
}

test('backtest parser recalculates metrics and explicitly marks incomplete gates', () => {
  const result = parseResult(fixture(), { strategy: 'TestStrategy', fee: 0.0004, slippage: 0.0005 });
  assert.equal(result.trades, 400);
  assert.ok(result.expectedValue > 0);
  assert.ok(result.profitFactor > 1);
  assert.equal(result.maxDrawdown, 0.12);
  assert.equal(result.assumptions.some((item) => item.includes('资金费率')), true);
  assert.equal(result.evalResult.complete, false);
  assert.equal(result.evalResult.gates.G7.status, 'not_evaluated');
});

test('G1-G10 evaluation cannot pass when required evidence is absent', () => {
  const result = parseResult(fixture(), { strategy: 'TestStrategy', slippage: 0 });
  const evaluated = evaluate(result, {});
  assert.equal(evaluated.passed, false);
  assert.equal(evaluated.gates.G4.pass, false);
  assert.equal(evaluated.gates.G10.pass, false);
});

test('backtest submission validates all command-bound fields', () => {
  assert.equal(validateSubmit({ strategy: 'CK_Trend_15m' }).timeframe, '15m');
  assert.throws(() => validateSubmit({ strategy: 'Bad; rm' }), /策略名称/);
  assert.throws(() => validateSubmit({ strategy: 'Good', configPath: '/tmp/config.json' }), /配置文件/);
  assert.throws(() => validateSubmit({ strategy: 'Good', container: 'bad name' }), /容器名称/);
});

test('backtest queue runs one job and stores the parsed report', async (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-backtest-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const calls = [];
  const runner = async (args) => {
    calls.push(args);
    if (args[0] === 'exec' && args.includes('sh')) return { code: 0, stdout: '/CK_Quant/user_data/backtest_results/desktop_job_result.json\n', stderr: '' };
    if (args[0] === 'cp') {
      fs.writeFileSync(args[2], JSON.stringify(fixture('TestStrategy', 40)));
      return { code: 0, stdout: '', stderr: '' };
    }
    return { code: 0, stdout: 'Backtesting complete\n', stderr: '' };
  };
  const service = new BacktestService({ store: new JsonStore(temp), dataDir: temp, send: () => {}, runner });
  const submitted = service.submit({ strategy: 'TestStrategy', timerange: '20240101-20260101', detail1m: true });
  assert.equal(submitted.ok, true);
  for (let tries = 0; tries < 100 && service.get(submitted.jobId)?.status !== 'done'; tries += 1) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  const job = service.get(submitted.jobId);
  assert.equal(job.status, 'done');
  assert.equal(job.result.trades, 40);
  const command = calls.find((args) => args.includes('backtesting'));
  assert.equal(command.includes('--timeframe-detail'), true);
  assert.equal(command.includes('--fee'), true);
});
