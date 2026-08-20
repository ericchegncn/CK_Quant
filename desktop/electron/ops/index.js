const { JsonStore } = require('../core/store');
const { OpsService } = require('./service');

function registerOpsHandlers(ipcMain, ctx) {
  const service = new OpsService({ store: new JsonStore(ctx.dataDir), ...ctx });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };
  ipcMain.handle('monitor:overview', () => guard() || { ok: true, snapshot: service.latest() });
  ipcMain.handle('monitor:inspect', async () => guard() || { ok: true, snapshot: await service.inspectAll({ source: 'manual' }) });
  ipcMain.handle('ops:diag', (_event, input) => {
    const denied = guard(); if (denied) return denied;
    const report = service.diagnostic(input?.serverId);
    return report ? { ok: true, report } : { ok: false, error: '尚无该服务器的巡检数据' };
  });
  ipcMain.handle('ops:report', () => guard() || { ok: true, report: service.report() });
  ipcMain.handle('ops:getSettings', () => guard() || { ok: true, settings: service.settings() });
  ipcMain.handle('ops:saveSettings', (_event, input) => guard() || { ok: true, settings: service.saveSettings(input) });
  return service;
}

module.exports = { registerOpsHandlers };
