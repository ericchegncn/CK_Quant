const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { validateStrategy } = require('../electron/strategy/validator');
const { StrategyLibraryService } = require('../electron/strategy/service');

const validFacts = {
  ok: true, classes: ['SafeStrategy'], imports: ['pandas', 'freqtrade.strategy'], calls: [], lines: 40,
  attributes: { SafeStrategy: { timeframe: '15m', use_custom_stoploss: false, atr_multiplier: 4 } },
  methods: { SafeStrategy: ['leverage', 'custom_exit', 'populate_indicators'] },
};

test('strategy validator enforces class, timeframe, future-data and import boundaries', async () => {
  const valid = await validateStrategy({ name: 'SafeStrategy', code: 'class SafeStrategy:\n    pass', strictTemplate: true, inspectImpl: async () => validFacts });
  assert.equal(valid.ok, true);

  const dangerous = await validateStrategy({
    name: 'SafeStrategy', code: 'future_value = shift(-1)', strictTemplate: true,
    inspectImpl: async () => ({ ...validFacts, imports: ['os'], calls: ['open'] }),
  });
  assert.equal(dangerous.ok, false);
  assert.equal(dangerous.errors.some((item) => item.rule === 'V5'), true);
  assert.equal(dangerous.errors.filter((item) => item.rule === 'V8').length, 2);
});

test('ordinary user strategy warns for missing core callbacks while locked template rejects it', async () => {
  const facts = { ...validFacts, methods: { SafeStrategy: [] } };
  const ordinary = await validateStrategy({ name: 'SafeStrategy', code: 'class SafeStrategy: pass', inspectImpl: async () => facts });
  const template = await validateStrategy({ name: 'SafeStrategy', code: 'class SafeStrategy: pass', strictTemplate: true, inspectImpl: async () => facts });
  assert.equal(ordinary.ok, true);
  assert.equal(ordinary.warnings.some((item) => item.rule === 'V4'), true);
  assert.equal(template.ok, false);
});

test('strategy library stores code locally and prevents locked template edits or deletion', async (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-strategy-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const validateImpl = async () => ({ ok: true, errors: [], warnings: [], facts: validFacts });
  const service = new StrategyLibraryService({ store: new JsonStore(temp), dataDir: temp, validateImpl });
  const saved = await service.save({ name: 'SafeStrategy', code: '# private strategy', locked: true, source: 'template' });
  assert.equal(saved.ok, true);
  assert.equal(service.read('SafeStrategy').code, '# private strategy');
  assert.equal((await service.save({ name: 'SafeStrategy', code: '# changed' })).code, 'STRATEGY_LOCKED');
  assert.equal(service.delete('SafeStrategy').ok, false);
  assert.equal(fs.existsSync(path.join(temp, 'strategies', 'SafeStrategy.py')), true);
});

test('strategy library creates a recoverable backup when an editable strategy changes', async (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-strategy-edit-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const validateImpl = async () => ({ ok: true, errors: [], warnings: [], facts: validFacts });
  const service = new StrategyLibraryService({ store: new JsonStore(temp), dataDir: temp, validateImpl });
  await service.save({ name: 'SafeStrategy', code: '# version 1' });
  await service.save({ name: 'SafeStrategy', code: '# version 2' });
  assert.equal(fs.readFileSync(path.join(temp, 'strategies', 'SafeStrategy.py.bak'), 'utf8'), '# version 1');
  assert.equal(service.read('SafeStrategy').code, '# version 2');
});
