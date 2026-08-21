const crypto = require('crypto');
const http = require('http');

function createPkce() {
  const verifier = crypto.randomBytes(48).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

function buildOpenRouterAuthUrl(callbackUrl, challenge) {
  const url = new URL('https://openrouter.ai/auth');
  url.searchParams.set('callback_url', callbackUrl);
  url.searchParams.set('code_challenge', challenge);
  url.searchParams.set('code_challenge_method', 'S256');
  return url.toString();
}

async function exchangeOpenRouterCode(code, verifier, fetchImpl = globalThis.fetch) {
  const response = await fetchImpl('https://openrouter.ai/api/v1/auth/keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, code_verifier: verifier, code_challenge_method: 'S256' }),
  });
  const detail = await response.text();
  if (!response.ok) throw new Error(`OpenRouter OAuth 交换失败（${response.status}）：${detail.slice(0, 300)}`);
  const payload = JSON.parse(detail);
  if (!payload.key) throw new Error('OpenRouter OAuth 未返回可用凭据');
  return payload.key;
}

class OAuthService {
  constructor({ settings, openExternal, fetchImpl = globalThis.fetch }) {
    this.settings = settings;
    this.openExternal = openExternal;
    this.fetch = fetchImpl;
    this.pending = null;
  }

  async connect(providerId) {
    if (providerId !== 'openrouter') throw new Error('该模型厂商暂未开放可安全使用的 OAuth 登录');
    if (this.pending) throw new Error('已有 OAuth 登录正在进行，请先在浏览器中完成');
    this.pending = true;
    const { verifier, challenge } = createPkce();
    const callbackToken = crypto.randomBytes(18).toString('base64url');
    let server;
    let timeout;
    try {
      const result = await new Promise((resolve, reject) => {
        server = http.createServer(async (request, response) => {
          try {
            const requestUrl = new URL(request.url, 'http://127.0.0.1');
            if (requestUrl.pathname !== `/oauth/openrouter/${callbackToken}`) {
              response.writeHead(404).end('Not found');
              return;
            }
            const code = requestUrl.searchParams.get('code');
            const error = requestUrl.searchParams.get('error');
            if (!code) throw new Error(error ? `用户未授权：${error}` : 'OAuth 回调缺少授权码');
            response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
            response.end('<!doctype html><meta charset="utf-8"><title>CK Quant</title><h2>OpenRouter 授权完成</h2><p>可以关闭此页面并返回 CK Quant Desktop。</p>');
            const apiKey = await exchangeOpenRouterCode(code, verifier, this.fetch);
            const current = this.settings.getPublic();
            this.settings.save({
              provider: 'openrouter',
              baseUrl: 'https://openrouter.ai/api/v1',
              model: current.provider === 'openrouter' ? current.model : '~openai/gpt-latest',
              apiKey,
              temperature: current.temperature,
              maxTokens: current.maxTokens,
            });
            resolve({ ok: true, provider: 'openrouter' });
          } catch (error) {
            if (!response.headersSent) {
              response.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
              response.end('CK Quant OAuth 登录失败，请返回软件查看错误。');
            }
            reject(error);
          }
        });
        server.once('error', reject);
        server.listen(0, '127.0.0.1', async () => {
          const port = server.address().port;
          const callbackUrl = `http://localhost:${port}/oauth/openrouter/${callbackToken}`;
          try {
            await this.openExternal(buildOpenRouterAuthUrl(callbackUrl, challenge));
          } catch (error) { reject(error); }
        });
        timeout = setTimeout(() => reject(new Error('OAuth 登录等待超时，请重新开始')), 5 * 60 * 1000);
      });
      return result;
    } finally {
      clearTimeout(timeout);
      if (server) server.close();
      this.pending = null;
    }
  }
}

module.exports = { OAuthService, createPkce, buildOpenRouterAuthUrl, exchangeOpenRouterCode };
