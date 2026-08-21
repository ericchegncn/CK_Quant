const assert = require('node:assert/strict');
const test = require('node:test');
const { LLM } = require('../electron/ai/llm');

const settings = { baseUrl: 'https://mock.example/v1', model: 'mock-model', apiKey: 'test', timeoutMs: 2000 };

test('LLM parses streamed content and fragmented tool calls', async () => {
  const events = [
    { choices: [{ delta: { content: '正在' } }] },
    { choices: [{ delta: { content: '查询' } }] },
    { choices: [{ delta: { tool_calls: [{ index: 0, id: 'call-1', function: { name: 'robot_', arguments: '{"serverId":' } }] } }] },
    { choices: [{ delta: { tool_calls: [{ index: 0, function: { name: 'status', arguments: '"srv-1"}' } }] } }] },
  ];
  const body = `${events.map((item) => `data: ${JSON.stringify(item)}\n\n`).join('')}data: [DONE]\n\n`;
  const llm = new LLM(settings, async () => new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } }));
  const deltas = [];
  const result = await llm.chat({ messages: [], tools: [{}], onDelta: (value) => deltas.push(value) });
  assert.equal(result.content, '正在查询');
  assert.deepEqual(deltas, ['正在', '查询']);
  assert.deepEqual(result.toolCalls, [{ id: 'call-1', name: 'robot_status', arguments: { serverId: 'srv-1' } }]);
});

test('LLM retries transient server failures twice', async () => {
  let attempts = 0;
  const llm = new LLM(settings, async () => {
    attempts += 1;
    if (attempts < 3) return new Response('temporary', { status: 503 });
    return new Response(JSON.stringify({ choices: [{ message: { content: 'OK' } }], model: 'mock-model' }), {
      status: 200, headers: { 'content-type': 'application/json' },
    });
  });
  const result = await llm.test();
  assert.equal(result.ok, true);
  assert.equal(attempts, 3);
});

test('LLM preserves malformed tool arguments without crashing', async () => {
  const payload = { choices: [{ message: { content: '', tool_calls: [{ id: 'bad', function: { name: 'robot_status', arguments: '{bad' } }] } }] };
  const llm = new LLM(settings, async () => new Response(JSON.stringify(payload), { status: 200, headers: { 'content-type': 'application/json' } }));
  const result = await llm.chat({ messages: [], tools: [{}] });
  assert.deepEqual(result.toolCalls[0].arguments, { _raw: '{bad' });
});

test('LLM supports local Ollama without an API key', async () => {
  let authorization;
  const llm = new LLM({ provider: 'ollama', baseUrl: 'http://127.0.0.1:11434/v1', model: 'qwen3:8b', apiKey: '', timeoutMs: 2000 }, async (_url, options) => {
    authorization = options.headers.Authorization;
    return new Response(JSON.stringify({ choices: [{ message: { content: 'OK' } }], model: 'qwen3:8b' }), {
      status: 200, headers: { 'content-type': 'application/json' },
    });
  });
  const result = await llm.test();
  assert.equal(result.ok, true);
  assert.equal(authorization, undefined);
});

test('LLM converts OpenAI tool definitions and results for Anthropic', async () => {
  let requestBody;
  const llm = new LLM({ provider: 'anthropic', baseUrl: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-6', apiKey: 'claude-key', timeoutMs: 2000 }, async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return new Response(JSON.stringify({
      model: 'claude-sonnet-4-6',
      content: [{ type: 'text', text: '正在查询' }, { type: 'tool_use', id: 'tool-1', name: 'robot_status', input: {} }],
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  });
  const result = await llm.chat({
    messages: [{ role: 'system', content: '系统' }, { role: 'user', content: '状态' }],
    tools: [{ type: 'function', function: { name: 'robot_status', description: '状态', parameters: { type: 'object' } } }],
  });
  assert.equal(requestBody.system, '系统');
  assert.equal(requestBody.tools[0].input_schema.type, 'object');
  assert.equal(result.content, '正在查询');
  assert.deepEqual(result.toolCalls, [{ id: 'tool-1', name: 'robot_status', arguments: {} }]);
});

test('LLM authentication errors explain provider mismatch without exposing the key', async () => {
  const apiKey = 'sk-secret-value-1234567890';
  const llm = new LLM({ provider: 'openai', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4.1-mini', apiKey, timeoutMs: 2000 }, async () => new Response(`invalid ${apiKey}`, { status: 401 }));
  await assert.rejects(() => llm.test(), (error) => {
    assert.equal(error.code, 'LLM_AUTH_ERROR');
    assert.match(error.message, /Key 与所选模型厂商不匹配/);
    assert.equal(error.message.includes(apiKey), false);
    return true;
  });
});
