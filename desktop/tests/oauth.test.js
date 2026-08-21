const assert = require('node:assert/strict');
const test = require('node:test');
const { createPkce, buildOpenRouterAuthUrl, exchangeOpenRouterCode } = require('../electron/ai/oauth');
const { publicProviders } = require('../electron/ai/providers');

test('OpenRouter OAuth uses a strong S256 PKCE challenge and localhost callback', () => {
  const { verifier, challenge } = createPkce();
  assert.ok(verifier.length >= 43);
  assert.ok(challenge.length >= 43);
  assert.notEqual(verifier, challenge);
  const authUrl = new URL(buildOpenRouterAuthUrl('http://localhost:54321/oauth/openrouter/random', challenge));
  assert.equal(authUrl.origin, 'https://openrouter.ai');
  assert.equal(authUrl.searchParams.get('callback_url'), 'http://localhost:54321/oauth/openrouter/random');
  assert.equal(authUrl.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(authUrl.searchParams.get('code_challenge'), challenge);
});

test('OpenRouter OAuth exchanges the code without exposing implementation secrets', async () => {
  let body;
  const key = await exchangeOpenRouterCode('authorization-code', 'verifier-value', async (_url, options) => {
    body = JSON.parse(options.body);
    return new Response(JSON.stringify({ key: 'openrouter-user-key' }), { status: 200 });
  });
  assert.equal(key, 'openrouter-user-key');
  assert.deepEqual(body, {
    code: 'authorization-code',
    code_verifier: 'verifier-value',
    code_challenge_method: 'S256',
  });
});

test('provider registry advertises OAuth only when implemented', () => {
  const providers = publicProviders();
  assert.deepEqual(providers.find((item) => item.id === 'openrouter').authMethods, ['api_key', 'oauth_pkce']);
  assert.deepEqual(providers.find((item) => item.id === 'openai').authMethods, ['api_key']);
  assert.deepEqual(providers.find((item) => item.id === 'ollama').authMethods, ['none']);
});
