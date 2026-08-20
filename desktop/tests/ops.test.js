const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { OpsService, redact, errorLines, extractProfit } = require('../electron/ops/service');

function tempStore(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-ops-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return new JsonStore(directory);
}

test('ops redaction removes credentials and long tokens from log evidence', () => {
  const value = redact('ERROR api_key=abcdefghijklmnopqrstuvwxyz1234567890 password: secret-value');
  assert.equal(value.includes('abcdefghijklmnopqrstuvwxyz1234567890'), false);
  assert.equal(value.includes('secret-value'), false);
  assert.equal(errorLines(`INFO ok\n${value}`).length, 1);
});

test('ops profit extraction combines closed and open data without inventing missing ratios', () => {
  const result = extractProfit(
    { profit_all_coin: 12.5, profit_all_ratio: 0.08, closed_trade_count: 20, max_drawdown: 5.2 },
    { data: [{ abs_profit: -2, rel_profit: -0.015 }] },
    [{ id: 1 }, { id: 2 }],
  );
  assert.equal(result.totalProfit, 12.5);
  assert.equal(result.openTrades, 2);
  assert.ok(Math.abs(result.maxDrawdown - 0.052) < 1e-12);
  assert.equal(result.dailyProfitRatio, -0.015);
});

test('manual inspection collects real facts but never exposes API credentials', async (t) => {
  const store = tempStore(t);
  const ssh = {
    exec: async (command) => {
      if (command.includes('docker inspect')) return { code: 0, stdout: 'running|2\n', stderr: '' };
      if (command.includes('docker logs')) return { code: 0, stdout: 'INFO ok\nERROR Timeout token=abcdefghijklmnopqrstuvwxyz1234567890', stderr: '' };
      if (command.includes('docker stats')) return { code: 0, stdout: '{"CPUPerc":"2.1%","MemUsage":"100MiB / 1GiB"}', stderr: '' };
      if (command.includes('df -P')) return { code: 0, stdout: '/dev/sda 100 40 60 40% /', stderr: '' };
      if (command.includes('stat -c')) return { code: 0, stdout: '1048576|1787200000', stderr: '' };
      if (command.includes('/ping')) return { code: 0, stdout: '{"status":"pong"}', stderr: '' };
      if (command.includes('/profit')) return { code: 0, stdout: '{"profit_all_coin":5,"profit_all_ratio":0.03,"max_drawdown":0.02}', stderr: '' };
      if (command.includes('/status')) return { code: 0, stdout: '[{"id":1}]', stderr: '' };
      if (command.includes('/daily')) return { code: 0, stdout: '{"data":[{"abs_profit":1,"rel_profit":0.01}]}', stderr: '' };
      return { code: 1, stdout: '', stderr: 'unknown' };
    },
  };
  const service = new OpsService({ store, getServers: () => [{ id: 's1', name: '测试机', host: '127.0.0.1', apiUsername: 'user', apiPassword: 'super-secret' }], ensureConnection: async () => ssh, robotAction: async () => ({ ok: true }), send: () => {}, wait: async () => {} });
  const snapshot = await service.inspectAll();
  assert.equal(snapshot.robots[0].state, 'running');
  assert.equal(snapshot.robots[0].api.state, 'ok');
  assert.equal(snapshot.robots[0].profit.openTrades, 1);
  assert.equal(JSON.stringify(snapshot).includes('super-secret'), false);
  assert.equal(JSON.stringify(snapshot).includes('abcdefghijklmnopqrstuvwxyz1234567890'), false);
});

test('self-heal respects manual stop and pauses a running robot on verified loss limit', async (t) => {
  const store = tempStore(t);
  const actions = [];
  const service = new OpsService({ store, getServers: () => [], ensureConnection: async () => null, robotAction: async (serverId, action) => { actions.push({ serverId, action }); return { ok: true }; }, send: () => {}, wait: async () => {} });
  service.saveSettings({ autoHeal: true, dailyLossLimit: 0.10, drawdownLimit: 0.30 });
  await service.applyRules({ robots: [
    { robotId: 'manual', serverId: 's1', serverName: '手动停止', desiredState: 'stopped', state: 'exited', api: { state: 'error' }, errors: [], profit: {}, diskPercent: 20 },
    { robotId: 'risk', serverId: 's2', serverName: '风险机器人', desiredState: 'running', state: 'running', api: { state: 'ok' }, errors: [], profit: { dailyProfitRatio: -0.12, maxDrawdown: 0.15 }, diskPercent: 20 },
  ] });
  assert.deepEqual(actions, [{ serverId: 's2', action: 'stop' }]);
  service.stop();
});
