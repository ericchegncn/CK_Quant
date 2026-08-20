const fs = require('fs');
const path = require('path');
const { validateStrategy } = require('./validator');

function now() { return new Date().toISOString(); }
function validName(name) { return /^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(String(name || '')); }

class StrategyLibraryService {
  constructor({ store, dataDir, validateImpl = validateStrategy }) {
    this.store = store;
    this.validateImpl = validateImpl;
    this.directory = path.join(dataDir, 'strategies');
    fs.mkdirSync(this.directory, { recursive: true });
  }

  load() { return this.store.read('strategy_index', { _schema: 1, strategies: [] }); }

  list() {
    return this.load().strategies.map((item) => ({ ...item, exists: fs.existsSync(path.join(this.directory, item.file)) }));
  }

  getMeta(name) { return this.load().strategies.find((item) => item.name === name); }

  read(name) {
    const meta = this.getMeta(name);
    if (!meta) return null;
    const filename = path.join(this.directory, meta.file);
    if (!fs.existsSync(filename)) return null;
    return { meta, code: fs.readFileSync(filename, 'utf8') };
  }

  async save(input = {}) {
    const name = String(input.name || '').trim();
    const code = String(input.code || '');
    if (!validName(name)) return { ok: false, error: '策略名称不合法', errors: [] };
    const existing = this.getMeta(name);
    if (existing?.locked) return { ok: false, error: '核心模板已锁定，只能另存为新策略', code: 'STRATEGY_LOCKED' };
    const locked = Boolean(input.locked);
    const validation = await this.validateImpl({ name, code, strictTemplate: locked });
    if (!validation.ok) return { ok: false, error: '策略校验未通过', ...validation, code: 'STRATEGY_INVALID' };

    const filename = `${name}.py`;
    const target = path.join(this.directory, filename);
    const temporary = `${target}.tmp-${process.pid}-${Date.now()}`;
    fs.writeFileSync(temporary, code, { encoding: 'utf8', mode: 0o600 });
    if (fs.existsSync(target)) fs.copyFileSync(target, `${target}.bak`);
    fs.renameSync(temporary, target);
    let saved;
    this.store.update('strategy_index', { _schema: 1, strategies: [] }, (data) => {
      const index = data.strategies.findIndex((item) => item.name === name);
      const createdAt = index >= 0 ? data.strategies[index].createdAt : now();
      saved = {
        ...(index >= 0 ? data.strategies[index] : {}), name, file: filename,
        source: ['template', 'variant', 'user', 'official'].includes(input.source) ? input.source : 'user',
        base: String(input.base || existing?.base || '').slice(0, 128), status: existing?.status || 'draft',
        locked, createdAt, updatedAt: now(), backtestIds: existing?.backtestIds || [], evalId: existing?.evalId || null,
        warnings: validation.warnings.map((item) => item.message), notes: String(input.notes || existing?.notes || '').slice(0, 1000),
      };
      if (index >= 0) data.strategies[index] = saved; else data.strategies.push(saved);
      return data;
    });
    this.store.appendAudit({ actor: 'user', action: 'strategy.localSave', params: { name, locked, source: saved.source }, result: 'ok' });
    return { ok: true, strategy: saved, validation };
  }

  async importFile(filename, locked = false) {
    const resolved = path.resolve(String(filename || ''));
    if (path.extname(resolved).toLowerCase() !== '.py' || !fs.existsSync(resolved)) return { ok: false, error: '请选择有效的 Python 策略文件' };
    const name = path.basename(resolved, '.py');
    const code = fs.readFileSync(resolved, 'utf8');
    return this.save({ name, code, locked, source: locked ? 'template' : 'user', notes: `从本机导入：${path.basename(resolved)}` });
  }

  delete(name) {
    const meta = this.getMeta(name);
    if (!meta) return { ok: false, error: '策略不存在' };
    if (meta.locked) return { ok: false, error: '核心模板已锁定，不能删除' };
    const filename = path.join(this.directory, meta.file);
    if (fs.existsSync(filename)) fs.renameSync(filename, `${filename}.deleted-${Date.now()}`);
    this.store.update('strategy_index', { _schema: 1, strategies: [] }, (data) => { data.strategies = data.strategies.filter((item) => item.name !== name); return data; });
    this.store.appendAudit({ actor: 'user', action: 'strategy.localDelete', params: { name }, result: 'ok' });
    return { ok: true };
  }

  setStatus(name, status) {
    const allowed = new Set(['draft', 'backtesting', 'passed', 'rejected', 'paper', 'live', 'banned']);
    if (!allowed.has(status)) return { ok: false, error: '策略状态不合法' };
    let found = false;
    this.store.update('strategy_index', { _schema: 1, strategies: [] }, (data) => {
      const item = data.strategies.find((strategy) => strategy.name === name);
      if (item) { item.status = status; item.updatedAt = now(); found = true; }
      return data;
    });
    return found ? { ok: true } : { ok: false, error: '策略不存在' };
  }
}

module.exports = { StrategyLibraryService, validName };
