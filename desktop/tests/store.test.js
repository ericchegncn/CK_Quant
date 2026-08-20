const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');

test('json store writes schema, updates atomically and keeps backups', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-store-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const store = new JsonStore(temp);
  store.write('settings', { value: 1 });
  store.update('settings', {}, (current) => ({ ...current, value: 2 }));
  assert.equal(store.read('settings').value, 2);
  assert.equal(store.read('settings')._schema, 1);
  assert.equal(JSON.parse(fs.readFileSync(path.join(temp, 'settings.json.bak.1'), 'utf8')).value, 1);
});

test('json store rejects path traversal names', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-store-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const store = new JsonStore(temp);
  assert.throws(() => store.path('../secret'), /非法数据文件名称/);
});
