const { URL } = require('url');
const { getProvider } = require('./providers');

const DEFAULTS = {
  _schema: 2,
  provider: 'deepseek',
  protocol: 'openai',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-v4-flash',
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
    const encrypted = settings.encryptedApiKeys?.[settings.provider] || settings.encryptedApiKey;
    if (!encrypted) return '';
    try {
      return this.safeStorage.decryptString(Buffer.from(encrypted, 'base64'));
    } catch (_) {
      return '';
    }
  }

  getPublic() {
    const settings = this.readRaw();
    return {
      baseUrl: settings.baseUrl,
      provider: settings.provider,
      protocol: settings.protocol,
      model: settings.model,
      hasKey: Boolean(settings.encryptedApiKeys?.[settings.provider] || settings.encryptedApiKey),
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
    const provider = getProvider(input.provider || current.provider);
    const protocol = provider.id === 'custom' && ['openai', 'anthropic'].includes(input.protocol)
      ? input.protocol : provider.protocol;
    const encryptedApiKeys = { ...(current.encryptedApiKeys || {}) };
    if (current.encryptedApiKey && current.provider && !encryptedApiKeys[current.provider]) {
      encryptedApiKeys[current.provider] = current.encryptedApiKey;
    }
    const requestedBaseUrl = input.baseUrl || provider.baseUrl || current.baseUrl;
    const next = {
      ...current,
      _schema: 2,
      provider: provider.id,
      protocol,
      encryptedApiKeys,
      baseUrl: normalizeBaseUrl(requestedBaseUrl),
      model: String(input.model || provider.models[0] || current.model).trim(),
      temperature: clampNumber(input.temperature, current.temperature, 0, 1),
      maxTokens: Math.round(clampNumber(input.maxTokens, current.maxTokens, 256, 32768)),
      timeoutMs: Math.round(clampNumber(input.timeoutMs, current.timeoutMs, 10000, 300000)),
      updatedAt: new Date().toISOString(),
    };
    if (!next.model) throw new Error('模型名称不能为空');
    if (provider.requiresKey && !input.apiKey && !encryptedApiKeys[provider.id]) throw new Error(`${provider.label} 需要 API Key`);
    if (input.apiKey) next.encryptedApiKeys[provider.id] = this.safeStorage.encryptString(String(input.apiKey).trim()).toString('base64');
    delete next.encryptedApiKey;
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
