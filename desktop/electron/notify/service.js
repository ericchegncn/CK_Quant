const http = require('http');
const https = require('https');
const tls = require('tls');

const DEFAULTS = { _schema: 1, desktopEnabled: true, telegramEnabled: false, proxyUrl: '', testedAt: null };

function validateProxy(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  const url = new URL(text);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('代理只支持 HTTP 或 HTTPS 地址');
  if (!url.hostname || !url.port) throw new Error('代理地址必须包含主机和端口，例如 http://127.0.0.1:7897');
  if (url.username || url.password) throw new Error('为避免明文保存代理密码，请使用无需认证的本机代理');
  return url.toString().replace(/\/$/, '');
}

function collectResponse(response, resolve, reject) {
  let data = '';
  response.on('data', (chunk) => { data += chunk.toString(); });
  response.on('end', () => {
    let json;
    try { json = JSON.parse(data); } catch (_) { json = null; }
    if (response.statusCode >= 200 && response.statusCode < 300 && json?.ok !== false) resolve(json || { ok: true });
    else reject(new Error(`Telegram 返回 HTTP ${response.statusCode}${json?.description ? `：${json.description}` : ''}`));
  });
}

function directPost(target, payload, timeoutMs) {
  return new Promise((resolve, reject) => {
    const body = Buffer.from(JSON.stringify(payload));
    const request = https.request(target, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': body.length } }, (response) => collectResponse(response, resolve, reject));
    request.setTimeout(timeoutMs, () => request.destroy(new Error('Telegram 请求超时')));
    request.on('error', reject);
    request.end(body);
  });
}

function proxyPost(target, payload, proxyUrl, timeoutMs) {
  return new Promise((resolve, reject) => {
    const proxy = new URL(proxyUrl);
    const connector = proxy.protocol === 'https:' ? https : http;
    const headers = { Host: `${target.hostname}:443` };
    if (proxy.username || proxy.password) headers['Proxy-Authorization'] = `Basic ${Buffer.from(`${decodeURIComponent(proxy.username)}:${decodeURIComponent(proxy.password)}`).toString('base64')}`;
    const connect = connector.request({ hostname: proxy.hostname, port: Number(proxy.port), method: 'CONNECT', path: `${target.hostname}:443`, headers });
    connect.setTimeout(timeoutMs, () => connect.destroy(new Error('连接 Telegram 代理超时')));
    connect.on('connect', (response, socket) => {
      if (response.statusCode !== 200) { socket.destroy(); reject(new Error(`代理 CONNECT 返回 ${response.statusCode}`)); return; }
      const secure = tls.connect({ socket, servername: target.hostname });
      secure.once('error', reject);
      secure.once('secureConnect', () => {
        const body = Buffer.from(JSON.stringify(payload));
        const request = https.request({ hostname: target.hostname, port: 443, path: `${target.pathname}${target.search}`, method: 'POST', createConnection: () => secure, agent: false, headers: { 'Content-Type': 'application/json', 'Content-Length': body.length } }, (telegramResponse) => collectResponse(telegramResponse, resolve, reject));
        request.setTimeout(timeoutMs, () => request.destroy(new Error('Telegram 请求超时')));
        request.on('error', reject);
        request.end(body);
      });
    });
    connect.on('error', reject);
    connect.end();
  });
}

async function telegramTransport({ token, chatId, text, proxyUrl = '', timeoutMs = 15000 }) {
  const target = new URL(`https://api.telegram.org/bot${token}/sendMessage`);
  const payload = { chat_id: chatId, text, parse_mode: 'HTML', disable_web_page_preview: true };
  return proxyUrl ? proxyPost(target, payload, proxyUrl, timeoutMs) : directPost(target, payload, timeoutMs);
}

class NotifyService {
  constructor({ store, safeStorage, desktopNotify = () => {}, transport = telegramTransport }) {
    this.store = store;
    this.safeStorage = safeStorage;
    this.desktopNotify = desktopNotify;
    this.transport = transport;
  }

  raw() { return { ...DEFAULTS, ...this.store.read('notifications', DEFAULTS) }; }

  secret(settings = this.raw()) {
    if (!settings.encryptedTelegramToken) return '';
    try { return this.safeStorage.decryptString(Buffer.from(settings.encryptedTelegramToken, 'base64')); }
    catch (_) { return ''; }
  }

  publicSettings() {
    const settings = this.raw();
    return { desktopEnabled: settings.desktopEnabled, telegramEnabled: settings.telegramEnabled, chatId: settings.chatId || '', proxyUrl: settings.proxyUrl || '', hasToken: Boolean(settings.encryptedTelegramToken), testedAt: settings.testedAt || null };
  }

  save(input = {}) {
    const current = this.raw();
    const chatId = String(input.chatId ?? current.chatId ?? '').trim();
    if (chatId && !/^-?\d{3,30}$/.test(chatId)) throw new Error('Telegram Chat ID 格式不正确');
    const next = {
      ...current,
      desktopEnabled: input.desktopEnabled !== false,
      telegramEnabled: Boolean(input.telegramEnabled),
      chatId,
      proxyUrl: validateProxy(input.proxyUrl ?? current.proxyUrl),
      updatedAt: new Date().toISOString(),
    };
    if (input.telegramToken) {
      if (!this.safeStorage.isEncryptionAvailable()) throw new Error('Windows 安全存储不可用，不能保存 Telegram Token');
      next.encryptedTelegramToken = this.safeStorage.encryptString(String(input.telegramToken).trim()).toString('base64');
    }
    if (next.telegramEnabled && (!next.encryptedTelegramToken || !next.chatId)) throw new Error('启用 Telegram 前必须填写 Bot Token 和 Chat ID');
    this.store.write('notifications', next);
    return this.publicSettings();
  }

  async send({ title, message, level = 'info' }) {
    const settings = this.raw();
    const channels = {};
    if (settings.desktopEnabled) {
      try { this.desktopNotify({ title, message, level }); channels.desktop = { ok: true }; }
      catch (error) { channels.desktop = { ok: false, error: error.message }; }
    }
    if (settings.telegramEnabled) {
      try {
        const token = this.secret(settings);
        if (!token || !settings.chatId) throw new Error('Telegram 凭据不完整');
        const icons = { info: 'ℹ️', warn: '⚠️', critical: '🔴' };
        await this.transport({ token, chatId: settings.chatId, proxyUrl: settings.proxyUrl, text: `${icons[level] || 'ℹ️'} <b>${String(title).replace(/[<>&]/g, '')}</b>\n${String(message).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}` });
        channels.telegram = { ok: true };
      } catch (error) { channels.telegram = { ok: false, error: String(error.message).replace(/bot[A-Za-z0-9:_-]+/g, 'bot[已隐藏]') }; }
    }
    return { ok: Object.values(channels).some((channel) => channel.ok), channels };
  }

  async test() {
    const result = await this.send({ title: 'CK Quant 通知测试', message: '如果你看到这条消息，通知配置已生效。', level: 'info' });
    if (result.channels.telegram?.ok) this.store.update('notifications', DEFAULTS, (settings) => ({ ...settings, testedAt: new Date().toISOString() }));
    return result;
  }
}

module.exports = { NotifyService, DEFAULTS, validateProxy, telegramTransport, directPost, proxyPost };
