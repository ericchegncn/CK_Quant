const crypto = require('crypto');
const { LLM } = require('./llm');
const { READ_TOOLS, WRITE_TOOLS } = require('./tools');

const SYSTEM_PROMPT = `你是 CK Quant 智能助手，服务不懂代码的中文用户。
规则：
1. 用简明中文回答，首次出现的技术词要解释。
2. 收益、回撤、订单、机器人状态和日志必须先调用工具取得真实数据；没有数据就明确说不知道。
3. 不承诺收益，不编造数据，不把回测当作实盘保证。
4. 任何重启、停止、部署、修改配置或资金相关操作都必须经过软件确认。
5. 用户私有策略内容不得发送到模型；只讨论公开框架和工具返回的摘要。
6. 回答优先给结论，再给证据来源和下一步建议。`;

function now() { return new Date().toISOString(); }

class ChatService {
  constructor({ store, settings, executeTool, confirmations, send }) {
    this.store = store;
    this.settings = settings;
    this.executeTool = executeTool;
    this.confirmations = confirmations;
    this.send = send;
    this.running = new Map();
  }

  load() { return this.store.read('chat_sessions', { _schema: 1, sessions: [] }); }

  getSession(sessionId, create = true) {
    const data = this.load();
    let session = data.sessions.find((item) => item.sessionId === sessionId);
    if (!session && create) {
      session = { sessionId: sessionId || `chat_${Date.now()}`, title: '新对话', createdAt: now(), updatedAt: now(), messages: [] };
      data.sessions.push(session);
      this.store.write('chat_sessions', data);
    }
    return session;
  }

  persistSession(session) {
    this.store.update('chat_sessions', { _schema: 1, sessions: [] }, (data) => {
      const index = data.sessions.findIndex((item) => item.sessionId === session.sessionId);
      session.messages = session.messages.slice(-100);
      session.updatedAt = now();
      if (index >= 0) data.sessions[index] = session; else data.sessions.push(session);
      return data;
    });
  }

  history(sessionId) {
    if (sessionId) return this.getSession(sessionId, false)?.messages || [];
    return this.load().sessions.map(({ sessionId: id, title, createdAt, updatedAt }) => ({ sessionId: id, title, createdAt, updatedAt }));
  }

  clear(sessionId) {
    this.store.update('chat_sessions', { _schema: 1, sessions: [] }, (data) => {
      if (sessionId) data.sessions = data.sessions.filter((item) => item.sessionId !== sessionId);
      else data.sessions = [];
      return data;
    });
    return { ok: true };
  }

  start(message, sessionId) {
    const text = String(message || '').trim();
    if (!text) return { ok: false, error: '请输入问题' };
    if (text.length > 12000) return { ok: false, error: '单次问题过长，请缩短后重试' };
    const session = this.getSession(sessionId || `chat_${Date.now()}`);
    if (this.running.has(session.sessionId)) return { ok: false, error: '当前会话仍在回答，请稍候' };
    const replyId = crypto.randomUUID();
    session.title = session.messages.length ? session.title : text.slice(0, 24);
    session.messages.push({ role: 'user', content: text, ts: now() });
    this.persistSession(session);
    const task = this.run(session, replyId).finally(() => this.running.delete(session.sessionId));
    this.running.set(session.sessionId, task);
    return { ok: true, sessionId: session.sessionId, replyId };
  }

  async run(session, replyId) {
    let finalText = '';
    try {
      const settings = this.settings.getWithSecret();
      if (!settings.apiKey) throw Object.assign(new Error('请先在设置中配置模型 API Key'), { code: 'LLM_NOT_CONFIGURED' });
      const llm = new LLM(settings);
      const messages = [{ role: 'system', content: SYSTEM_PROMPT }, ...session.messages.slice(-30).map(({ role, content, toolCallId, name }) => ({ role, content, tool_call_id: toolCallId, name }))];
      for (let round = 0; round < 8; round += 1) {
        const streamed = [];
        const response = await llm.chat({ messages, tools: READ_TOOLS, onDelta: (delta) => {
          streamed.push(delta);
          this.send('ai:stream', { sessionId: session.sessionId, replyId, delta, ts: now() });
        } });
        finalText += response.content || streamed.join('');
        const assistant = { role: 'assistant', content: response.content || '', ts: now() };
        if (response.toolCalls.length) assistant.tool_calls = response.toolCalls.map((call) => ({ id: call.id, type: 'function', function: { name: call.name, arguments: JSON.stringify(call.arguments) } }));
        messages.push(assistant);
        if (!response.toolCalls.length) break;
        for (const call of response.toolCalls) {
          this.send('ai:tool', { sessionId: session.sessionId, replyId, tool: call.name, status: 'start', detail: call.arguments, ts: now() });
          let result;
          if (WRITE_TOOLS.has(call.name)) {
            const approved = await this.confirmations.request({
              sessionId: session.sessionId,
              replyId,
              action: { type: call.name, summary: `AI 请求执行 ${call.name}`, params: call.arguments },
            });
            result = approved ? await this.executeTool(call.name, call.arguments) : { ok: false, denied: true, error: '用户拒绝或确认超时' };
          } else result = await this.executeTool(call.name, call.arguments);
          this.store.appendAudit({ actor: WRITE_TOOLS.has(call.name) ? 'user' : 'ai', action: `tool.${call.name}`, params: call.arguments, result: result.ok ? 'ok' : 'error' });
          this.send('ai:tool', { sessionId: session.sessionId, replyId, tool: call.name, status: result.ok ? 'done' : 'error', detail: result, ts: now() });
          messages.push({ role: 'tool', tool_call_id: call.id, name: call.name, content: JSON.stringify(result).slice(0, 30000) });
        }
      }
      session.messages.push({ role: 'assistant', content: finalText || '操作已处理。', ts: now() });
      this.persistSession(session);
      this.send('ai:done', { sessionId: session.sessionId, replyId, final: finalText, ts: now() });
    } catch (error) {
      const message = error.message || 'AI 助手发生未知错误';
      session.messages.push({ role: 'assistant', content: `无法完成：${message}`, ts: now(), error: true });
      this.persistSession(session);
      this.send('ai:error', { sessionId: session.sessionId, replyId, error: message, code: error.code, ts: now() });
    }
  }
}

module.exports = { ChatService, SYSTEM_PROMPT };
