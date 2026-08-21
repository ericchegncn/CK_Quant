const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { JsonStore } = require('../electron/core/store');
const { AISettingsService, normalizeBaseUrl } = require('../electron/ai/settings');

test('AI settings encrypt the API key and never expose it publicly', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-ai-settings-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (value) => Buffer.from(`protected:${value}`),
    decryptString: (value) => value.toString().replace(/^protected:/, ''),
  };
  const service = new AISettingsService({ store: new JsonStore(temp), safeStorage });
  service.save({ provider: 'custom', baseUrl: 'https://api.example.com/v1/', model: 'model-a', apiKey: 'secret-key' });
  const disk = fs.readFileSync(path.join(temp, 'llm.json'), 'utf8');
  assert.equal(disk.includes('secret-key'), false);
  assert.equal(service.getPublic().hasKey, true);
  assert.equal(service.getPublic().apiKey, undefined);
  assert.equal(service.getWithSecret().apiKey, 'secret-key');
});

test('AI settings keep a separate encrypted key for every provider', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-ai-provider-'));
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (value) => Buffer.from(`protected:${value}`),
    decryptString: (value) => value.toString().replace(/^protected:/, ''),
  };
  const service = new AISettingsService({ store: new JsonStore(temp), safeStorage });
  service.save({ provider: 'deepseek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-v4-flash', apiKey: 'deepseek-secret' });
  assert.throws(() => service.save({ provider: 'openai', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4.1-mini' }), /OpenAI 需要 API Key/);
  service.save({ provider: 'openai', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4.1-mini', apiKey: 'openai-secret' });
  assert.equal(service.getWithSecret().apiKey, 'openai-secret');
  service.save({ provider: 'deepseek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-v4-flash' });
  assert.equal(service.getWithSecret().apiKey, 'deepseek-secret');
  fs.rmSync(temp, { recursive: true, force: true });
});

test('AI settings allow local HTTP but reject remote insecure HTTP', () => {
  assert.equal(normalizeBaseUrl('http://127.0.0.1:11434/v1/'), 'http://127.0.0.1:11434/v1');
  assert.throws(() => normalizeBaseUrl('http://api.example.com/v1'), /HTTPS/);
});
