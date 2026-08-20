const { URL } = require('url');

const DEFAULTS = {
  _schema: 1,
  baseUrl: 'https://api.deepseek.com/v1',
  model: 'deepseek-chat',
  temperature: 0.3,
  maxTokens: 4096,
  timeoutMs: 120000,
};

function normalizeBaseUrl(value) {
  const url = new URL(String(value || '').trim());
  const local = ['localhost', '127.0.0.1', '::1'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(local && url.protocol === 'http:')) {
    throw new Error('模型服务必须使用 HTTPS；仅本机 localhost 允许 HTTP');
  }
  url.pathname = url.pathname.replace(/\/+$/, '');
  url.search = '';
  url.hash = '';
  return url.toString().replace(/\/$/, '');
}

function clampNumber(value, fallback, min, max) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
}

class AISettingsService {
  constructor({ store, safeStorage }) {
    this.store = store;
    this.safeStorage = safeStorage;
  }

  readRaw() {
    return { ...DEFAULTS, ...this.store.read('llm', DEFAULTS) };
  }

  decryptKey(settings) {
    if (!settings.encryptedApiKey) return '';
    try {
      return this.safeStorage.decryptString(Buffer.from(settings.encryptedApiKey, 'base64'));
    } catch (_) {
      return '';
    }
  }

  getPublic() {
    const settings = this.readRaw();
    return {
      baseUrl: settings.baseUrl,
      model: settings.model,
      hasKey: Boolean(settings.encryptedApiKey),
      temperature: settings.temperature,
      maxTokens: settings.maxTokens,
      timeoutMs: settings.timeoutMs,
      testedAt: settings.testedAt || null,
      lastLatencyMs: settings.lastLatencyMs || null,
    };
  }

  getWithSecret() {
    const settings = this.readRaw();
    return { ...settings, apiKey: this.decryptKey(settings) };
  }

  save(input) {
    if (!this.safeStorage.isEncryptionAvailable()) throw new Error('Windows 安全存储当前不可用，不能保存 API Key');
    const current = this.readRaw();
    const next = {
      ...current,
      baseUrl: normalizeBaseUrl(input.baseUrl || current.baseUrl),
      model: String(input.model || current.model).trim(),
      temperature: clampNumber(input.temperature, current.temperature, 0, 1),
      maxTokens: Math.round(clampNumber(input.maxTokens, current.maxTokens, 256, 32768)),
      timeoutMs: Math.round(clampNumber(input.timeoutMs, current.timeoutMs, 10000, 300000)),
      updatedAt: new Date().toISOString(),
    };
    if (!next.model) throw new Error('模型名称不能为空');
    if (input.apiKey) next.encryptedApiKey = this.safeStorage.encryptString(String(input.apiKey).trim()).toString('base64');
    this.store.write('llm', next);
    return this.getPublic();
  }

  markTested(latencyMs) {
    this.store.update('llm', DEFAULTS, (settings) => ({
      ...settings,
      testedAt: new Date().toISOString(),
      lastLatencyMs: latencyMs,
    }));
  }
}

module.exports = { AISettingsService, DEFAULTS, normalizeBaseUrl };
