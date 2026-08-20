const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { AutopilotService, splitTimerange, marketRegime } = require('../electron/autopilot/service');
const { extractTunables, generateVariants, generateRandomBaseline } = require('../electron/autopilot/variants');

const templateCode = `class Core(IStrategy):
    timeframe = '15m'
    def leverage(self, **kwargs):
        return 2
    def custom_exit(self, **kwargs):
        return None
    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[(dataframe['atr'] > 0.002) & (dataframe['near'] < 1.5), 'enter_long'] = 1
        return dataframe
`;

test('variant generation changes only entry thresholds and class name', () => {
  assert.deepEqual(extractTunables(templateCode).map((item) => item.value), [0.002, 1.5]);
  const result = generateVariants({ name: 'Core', code: templateCode, count: 3 });
  assert.equal(result.variants.length, 3);
  assert.match(result.variants[0].code, /class AI_\d+_v1\(IStrategy\)/);
  assert.match(result.variants[0].code, /def custom_exit/);
  assert.match(result.variants[0].code, /return 2/);
  assert.notEqual(result.variants[0].code, result.variants[1].code);
});

test('random baseline preserves private risk callbacks and replaces only entry generation', () => {
  const baseline = generateRandomBaseline({ name: 'Core', code: templateCode });
  assert.match(baseline.code, /class Baseline_\d+\(_LocalCore_\d+\)/);
  assert.match(baseline.code, /def custom_exit/);
  assert.match(baseline.code, /random_key/);
  assert.equal(baseline.code.includes('shift(-'), false);
});

test('walk-forward ranges are deterministic and regimes use explicit thresholds', () => {
  assert.deepEqual(splitTimerange('20240101-20260101', 3, new Date('2026-01-01T00:00:00Z')), ['20240101-20240831', '20240831-20250502', '20250502-20260101']);
  assert.equal(marketRegime(0.2), 'bull');
  assert.equal(marketRegime(-0.2), 'bear');
  assert.equal(marketRegime(0.02), 'range');
});

test('autopilot performs local research, creates variants and stops honestly at incomplete gates', async (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-auto-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const strategiesByName = new Map([['Core', { meta: { name: 'Core', locked: true, source: 'official' }, code: templateCode }]]);
  const statuses = new Map();
  const strategies = {
    read: (name) => strategiesByName.get(name) || null,
    list: () => [{ name: 'Core', locked: true, source: 'official' }],
    save: async (input) => { const item = { meta: { name: input.name, locked: false }, code: input.code }; strategiesByName.set(input.name, item); return { ok: true, strategy: item.meta }; },
    setStatus: (name, status) => { statuses.set(name, status); return { ok: true }; },
    linkBacktest: () => ({ ok: true }),
  };
  const jobs = new Map(); let number = 0;
  const backtests = {
    submit: (input) => { const jobId = `job_${++number}`; jobs.set(jobId, { jobId, strategy: input.strategy, timerange: input.timerange, status: 'done', evalResult: { complete: false, passed: false, gates: { G3: { pass: true }, G4: { pass: true }, G5: { pass: true }, G6: { pass: true } } }, result: { trades: 50, expectedValue: 0.001, annualReturn: 0.1, marketChange: 0.02, maxDrawdown: 0.1, profitFactor: 1.1 } }); return { ok: true, jobId }; },
    wait: async (jobId) => jobs.get(jobId),
    get: (jobId) => jobs.get(jobId),
    reevaluate: (jobId) => { const job = jobs.get(jobId); job.evalResult = { complete: true, passed: false }; return { ok: true, evalResult: job.evalResult }; },
  };
  const service = new AutopilotService({
    store: new JsonStore(directory), send: () => {}, strategies, backtests,
    research: async () => ({ generatedAt: new Date().toISOString(), scanned: 3, candidates: [{ pair: 'BTC/USDT:USDT' }, { pair: 'ETH/USDT:USDT' }, { pair: 'SOL/USDT:USDT' }] }),
  });
  const started = service.start({ template: 'Core', variantCount: 3 });
  assert.equal(started.ok, true);
  for (let tries = 0; tries < 100 && service.current()?.state !== 'AWAITING_USER'; tries += 1) await new Promise((resolve) => setTimeout(resolve, 5));
  const run = service.current();
  assert.equal(run.state, 'AWAITING_USER');
  assert.equal(run.awaitingUser.type, 'improve_confirm');
  assert.equal(run.artifacts.strategies.length, 3);
  assert.equal(run.artifacts.backtestJobs.length, 3);
  assert.equal(run.artifacts.strategies.every((name) => statuses.get(name) === 'rejected'), true);
  assert.equal(JSON.stringify(new JsonStore(directory).read('autopilot')).includes(templateCode), false);
});

test('paper deployment requires explicit decision and tracking waits for minimum evidence', async (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-auto-paper-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const store = new JsonStore(directory);
  const run = {
    runId: 'auto_paper', state: 'AWAITING_USER', startedAt: new Date().toISOString(), updatedAt: new Date().toISOString(), endedAt: null,
    options: { paperServerId: 'server_1' }, current: { progress: 0.94 }, history: [], outcome: null,
    artifacts: { paperRobotId: null, evalReport: { rows: [{ strategy: 'PublicV1', metrics: { expectedValue: 0.001 } }] } },
    awaitingUser: { type: 'paper_confirm', payload: { candidates: ['PublicV1'] } },
  };
  store.write('autopilot', { _schema: 1, current: run, runs: [run] });
  let deployed = 0;
  const service = new AutopilotService({
    store, send: () => {}, backtests: {},
    strategies: { read: () => ({ meta: { name: 'PublicV1' }, code: '# public variant' }), setStatus: () => ({ ok: true }) },
    deployPaper: async () => { deployed += 1; return { ok: true }; },
  });
  assert.equal(deployed, 0);
  assert.equal((await service.decide({ decision: 'confirm' })).ok, true);
  assert.equal(deployed, 1);
  assert.equal(service.current().state, 'SIM_TRACKING');
  await service.observe({ ts: new Date().toISOString(), robot: { serverId: 'server_1', state: 'running', api: { state: 'ok' }, profit: { closedTrades: 10, totalProfitRatio: 0.01, maxDrawdown: 0.02 } } });
  assert.equal(service.current().state, 'SIM_TRACKING');
});
