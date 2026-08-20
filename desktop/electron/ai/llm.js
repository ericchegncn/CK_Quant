class LLMError extends Error {
  constructor(code, message, status = null) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

function endpoint(baseUrl, resource) {
  const base = String(baseUrl || '').replace(/\/+$/, '');
  if (resource === 'chat/completions' && /\/chat\/completions$/i.test(base)) return base;
  return `${base}/${resource}`;
}

function parseToolCalls(deltas) {
  return [...deltas.values()].map((call) => {
    let args = {};
    try { args = JSON.parse(call.arguments || '{}'); } catch (_) { args = { _raw: call.arguments || '' }; }
    return { id: call.id, name: call.name, arguments: args };
  });
}

function parseArguments(value) {
  try { return JSON.parse(value || '{}'); }
  catch (_) { return { _raw: value || '' }; }
}

function retryable(error) {
  return error?.name === 'TypeError' || error?.code === 'LLM_TIMEOUT' ||
    error?.status === 408 || error?.status === 429 || error?.status >= 500;
}

class LLM {
  constructor(settings, fetchImpl = globalThis.fetch) {
    this.settings = settings;
    this.fetch = fetchImpl;
    if (!fetchImpl) throw new Error('当前运行环境不支持 fetch');
  }

  headers() {
    if (!this.settings.apiKey) throw new LLMError('LLM_NOT_CONFIGURED', '请先在设置中填写模型 API Key');
    return { 'Content-Type': 'application/json', Authorization: `Bearer ${this.settings.apiKey}` };
  }

  async request(url, options, timeoutMs = this.settings.timeoutMs || 120000) {
    let lastError;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await this.fetch(url, { ...options, signal: controller.signal });
        if (!response.ok) {
          const detail = (await response.text()).slice(0, 500);
          const code = response.status === 429 ? 'LLM_RATE_LIMIT' : 'LLM_HTTP_ERROR';
          throw new LLMError(code, `模型服务返回 ${response.status}: ${detail || response.statusText}`, response.status);
        }
        return response;
      } catch (error) {
        lastError = error.name === 'AbortError'
          ? new LLMError('LLM_TIMEOUT', '模型请求超时，请检查网络或提高超时时间')
          : error;
        if (attempt >= 2 || !retryable(lastError)) throw lastError;
        await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastError;
  }

  async chat({ messages, tools = [], temperature, maxTokens, onDelta = () => {} }) {
    const response = await this.request(endpoint(this.settings.baseUrl, 'chat/completions'), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({
        model: this.settings.model,
        messages,
        tools: tools.length ? tools : undefined,
        tool_choice: tools.length ? 'auto' : undefined,
        temperature: temperature ?? this.settings.temperature ?? 0.3,
        max_tokens: maxTokens ?? this.settings.maxTokens ?? 4096,
        stream: true,
      }),
    });

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/event-stream')) {
      const json = await response.json();
      const message = json.choices?.[0]?.message;
      if (!message) throw new LLMError('LLM_INVALID_RESPONSE', '模型返回内容无法识别');
      if (message.content) onDelta(message.content);
      return {
        content: message.content || '',
        toolCalls: (message.tool_calls || []).map((call) => ({
          id: call.id,
          name: call.function?.name,
          arguments: parseArguments(call.function?.arguments),
        })),
      };
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let content = '';
    const calls = new Map();
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const data = line.slice(5).trim();
        if (!data || data === '[DONE]') continue;
        let event;
        try { event = JSON.parse(data); } catch (_) { continue; }
        const delta = event.choices?.[0]?.delta || {};
        if (delta.content) { content += delta.content; onDelta(delta.content); }
        for (const item of delta.tool_calls || []) {
          const current = calls.get(item.index) || { id: '', name: '', arguments: '' };
          if (item.id) current.id = item.id;
          if (item.function?.name) current.name += item.function.name;
          if (item.function?.arguments) current.arguments += item.function.arguments;
          calls.set(item.index, current);
        }
      }
      if (done) break;
    }
    return { content, toolCalls: parseToolCalls(calls) };
  }

  async test() {
    const started = Date.now();
    const response = await this.request(endpoint(this.settings.baseUrl, 'chat/completions'), {
      method: 'POST', headers: this.headers(), body: JSON.stringify({
        model: this.settings.model,
        messages: [{ role: 'user', content: '只回复 OK' }],
        temperature: 0,
        max_tokens: 8,
        stream: false,
      }),
    }, Math.min(this.settings.timeoutMs || 120000, 30000));
    const json = await response.json();
    if (!json.choices?.[0]?.message) throw new LLMError('LLM_INVALID_RESPONSE', '模型连接成功，但返回格式不兼容');
    return { ok: true, latencyMs: Date.now() - started, model: json.model || this.settings.model };
  }

  async listModels() {
    try {
      const response = await this.request(endpoint(this.settings.baseUrl, 'models'), { method: 'GET', headers: this.headers() }, 30000);
      const json = await response.json();
      return (json.data || []).map((item) => item.id).filter(Boolean);
    } catch (_) {
      return [];
    }
  }
}

module.exports = { LLM, LLMError, endpoint, parseToolCalls, parseArguments, retryable };
