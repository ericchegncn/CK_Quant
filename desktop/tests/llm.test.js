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
