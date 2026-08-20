const { JsonStore } = require('../core/store');
const { StrategyLibraryService } = require('./service');
const { validateStrategy } = require('./validator');

function registerStrategyLibraryHandlers(ipcMain, ctx) {
  const service = new StrategyLibraryService({ store: new JsonStore(ctx.dataDir), dataDir: ctx.dataDir });
  const guard = () => ctx.isLicensed() ? null : { ok: false, error: '软件尚未激活' };
  ipcMain.handle('strategy:localList', () => guard() || { ok: true, strategies: service.list() });
  ipcMain.handle('strategy:localRead', (_event, input) => {
    const denied = guard(); if (denied) return denied;
    const item = service.read(input?.name);
    return item ? { ok: true, ...item } : { ok: false, error: '策略不存在' };
  });
  ipcMain.handle('strategy:localSave', (_event, input) => guard() || service.save(input));
  ipcMain.handle('strategy:localDelete', (_event, input) => guard() || service.delete(input?.name));
  ipcMain.handle('strategy:setStatus', (_event, input) => guard() || service.setStatus(input?.name, input?.status));
  ipcMain.handle('strategy:validate', (_event, input) => guard() || validateStrategy({ name: input?.name, code: input?.code, strictTemplate: Boolean(input?.strictTemplate) }));
  ipcMain.handle('strategy:localImport', async (_event, input) => {
    const denied = guard(); if (denied) return denied;
    const selection = await ctx.dialog.showOpenDialog(ctx.getWindow(), { title: '导入本机策略', properties: ['openFile'], filters: [{ name: 'Freqtrade Python 策略', extensions: ['py'] }] });
    if (selection.canceled || !selection.filePaths[0]) return { ok: false, cancelled: true };
    return service.importFile(selection.filePaths[0], Boolean(input?.locked));
  });
  return service;
}

module.exports = { registerStrategyLibraryHandlers };
