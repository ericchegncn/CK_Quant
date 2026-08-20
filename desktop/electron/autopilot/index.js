const { JsonStore } = require('../core/store');
const { AutopilotService } = require('./service');

function registerAutopilotHandlers(ipcMain, ctx) {
  const service = new AutopilotService({ store: new JsonStore(ctx.dataDir), send: ctx.send, backtests: ctx.backtests, strategies: ctx.strategies, notify: ctx.notify, deployPaper: ctx.deployPaper });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };
  ipcMain.handle('autopilot:start', (_event, input) => guard() || service.start(input));
  ipcMain.handle('autopilot:status', () => guard() || service.status());
  ipcMain.handle('autopilot:pause', () => guard() || service.pause());
  ipcMain.handle('autopilot:resume', () => guard() || service.resume());
  ipcMain.handle('autopilot:history', (_event, input) => guard() || service.history(input?.limit));
  ipcMain.handle('autopilot:decide', (_event, input) => guard() || service.decide(input));
  return service;
}

module.exports = { registerAutopilotHandlers };
