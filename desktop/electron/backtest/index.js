const { JsonStore } = require('../core/store');
const { BacktestService } = require('./service');

function registerBacktestHandlers(ipcMain, ctx) {
  const service = new BacktestService({ store: new JsonStore(ctx.dataDir), dataDir: ctx.dataDir, send: ctx.send, strategyResolver: ctx.strategyResolver });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };
  ipcMain.handle('backtest:submit', (_event, input) => guard() || service.submit(input));
  ipcMain.handle('backtest:list', (_event, input) => guard() || { ok: true, jobs: service.list(input?.limit) });
  ipcMain.handle('backtest:get', (_event, input) => {
    const denied = guard(); if (denied) return denied;
    const job = service.get(input?.jobId);
    return job ? { ok: true, job } : { ok: false, error: '回测任务不存在' };
  });
  ipcMain.handle('backtest:cancel', (_event, input) => guard() || service.cancel(input?.jobId));
  ipcMain.handle('backtest:compare', (_event, input) => guard() || { ok: true, table: service.compare(input?.jobIds) });
  return service;
}

module.exports = { registerBacktestHandlers };
