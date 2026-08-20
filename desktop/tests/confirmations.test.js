const assert = require('node:assert/strict');
const test = require('node:test');
const { ConfirmationManager } = require('../electron/ai/confirmations');

test('write confirmation executes only after explicit approval', async () => {
  let request;
  const manager = new ConfirmationManager({ send: (_channel, payload) => { request = payload; }, timeoutMs: 1000 });
  const pending = manager.request({ action: { type: 'robot_action' } });
  assert.ok(request.confirmationId);
  assert.equal(manager.resolve(request.confirmationId, true), true);
  assert.equal(await pending, true);
  assert.equal(manager.resolve(request.confirmationId, true), false);
});

test('write confirmation denies on timeout', async () => {
  const manager = new ConfirmationManager({ send: () => {}, timeoutMs: 5 });
  assert.equal(await manager.request({ action: { type: 'robot_action' } }), false);
});
