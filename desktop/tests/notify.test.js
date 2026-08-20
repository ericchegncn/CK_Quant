const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { NotifyService, validateProxy } = require('../electron/notify/service');

function fixture(t, overrides = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-notify-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (value) => Buffer.from(`protected:${value}`),
    decryptString: (value) => value.toString().replace(/^protected:/, ''),
  };
  return { directory, service: new NotifyService({ store: new JsonStore(directory), safeStorage, desktopNotify: () => {}, ...overrides }) };
}

test('notification settings encrypt Telegram token and public settings never return it', (t) => {
  const { directory, service } = fixture(t);
  const settings = service.save({ telegramEnabled: true, telegramToken: '123456:private-token', chatId: '123456789', proxyUrl: 'http://127.0.0.1:7897' });
  const disk = fs.readFileSync(path.join(directory, 'notifications.json'), 'utf8');
  assert.equal(disk.includes('private-token'), false);
  assert.equal(settings.hasToken, true);
  assert.equal(settings.telegramToken, undefined);
  assert.equal(service.secret(), '123456:private-token');
});

test('proxy validation accepts local proxy syntax and rejects embedded credentials', () => {
  assert.equal(validateProxy('http://127.0.0.1:7897/'), 'http://127.0.0.1:7897');
  assert.throws(() => validateProxy('socks5://127.0.0.1:1080'), /HTTP/);
  assert.throws(() => validateProxy('http://user:pass@127.0.0.1:7897'), /代理密码/);
});

test('notification delivery uses desktop and Telegram without exposing token in result', async (t) => {
  const calls = [];
  const { service } = fixture(t, { desktopNotify: (message) => calls.push({ desktop: message }), transport: async (message) => { calls.push({ telegram: message }); return { ok: true }; } });
  service.save({ desktopEnabled: true, telegramEnabled: true, telegramToken: '123456:private-token', chatId: '123456789' });
  const result = await service.send({ title: '测试', message: '状态正常', level: 'info' });
  assert.equal(result.ok, true);
  assert.equal(result.channels.desktop.ok, true);
  assert.equal(result.channels.telegram.ok, true);
  assert.equal(calls.length, 2);
  assert.equal(JSON.stringify(result).includes('private-token'), false);
});
