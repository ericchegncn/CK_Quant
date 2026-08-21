const { JsonStore } = require('../core/store');
const { AISettingsService } = require('./settings');
const { LLM } = require('./llm');
const { ConfirmationManager } = require('./confirmations');
const { ChatService } = require('./chat');
const { createToolExecutor } = require('./tools');
const { publicProviders } = require('./providers');
const { OAuthService } = require('./oauth');

function registerAIHandlers(ipcMain, ctx) {
  const store = new JsonStore(ctx.dataDir);
  const settings = new AISettingsService({ store, safeStorage: ctx.safeStorage });
  const send = (channel, payload) => ctx.send(channel, payload);
  const confirmations = new ConfirmationManager({ send });
  const executeTool = createToolExecutor({ ...ctx, store });
  const chat = new ChatService({ store, settings, executeTool, confirmations, send });
  const oauth = new OAuthService({ settings, openExternal: ctx.openExternal });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };

  ipcMain.handle('ai:getSettings', () => guard() || { ok: true, settings: settings.getPublic() });
  ipcMain.handle('ai:getProviders', () => guard() || { ok: true, providers: publicProviders() });
  ipcMain.handle('ai:oauthConnect', async (_event, input) => {
    const denied = guard(); if (denied) return denied;
    try { return await oauth.connect(String(input?.provider || '')); }
    catch (error) { return { ok: false, error: error.message }; }
  });
  ipcMain.handle('ai:saveSettings', (_event, input) => {
    const denied = guard(); if (denied) return denied;
    try { return { ok: true, settings: settings.save(input || {}) }; }
    catch (error) { return { ok: false, error: error.message }; }
  });
  ipcMain.handle('ai:testConnection', async () => {
    const denied = guard(); if (denied) return denied;
    try {
      const result = await new LLM(settings.getWithSecret()).test();
      settings.markTested(result.latencyMs);
      return result;
    } catch (error) { return { ok: false, error: error.message, code: error.code }; }
  });
  ipcMain.handle('ai:listModels', async () => {
    const denied = guard(); if (denied) return denied;
    try { return { ok: true, models: await new LLM(settings.getWithSecret()).listModels() }; }
    catch (error) { return { ok: false, error: error.message, models: [] }; }
  });
  ipcMain.handle('ai:chat', (_event, input) => guard() || chat.start(input?.message, input?.sessionId));
  ipcMain.handle('ai:history', (_event, input) => guard() || { ok: true, messages: chat.history(input?.sessionId) });
  ipcMain.handle('ai:clear', (_event, input) => guard() || chat.clear(input?.sessionId));
  ipcMain.handle('ai:confirm', (_event, input) => guard() || { ok: confirmations.resolve(input?.confirmationId, input?.approved) });

  return { store, settings, chat, confirmations };
}

module.exports = { registerAIHandlers };
