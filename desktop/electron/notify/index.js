const { JsonStore } = require('../core/store');
const { NotifyService } = require('./service');

function registerNotifyHandlers(ipcMain, ctx) {
  const service = new NotifyService({ store: new JsonStore(ctx.dataDir), safeStorage: ctx.safeStorage, desktopNotify: ctx.desktopNotify });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };
  ipcMain.handle('notify:getSettings', () => guard() || { ok: true, settings: service.publicSettings() });
  ipcMain.handle('notify:saveSettings', (_event, input) => {
    const denied = guard(); if (denied) return denied;
    try { return { ok: true, settings: service.save(input) }; }
    catch (error) { return { ok: false, error: error.message }; }
  });
  ipcMain.handle('notify:test', async () => guard() || service.test());
  return service;
}

module.exports = { registerNotifyHandlers };
