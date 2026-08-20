const fs = require('fs');
const path = require('path');

function assertName(name) {
  if (!/^[a-z0-9_-]+$/i.test(String(name || ''))) throw new Error('非法数据文件名称');
}

class JsonStore {
  constructor(baseDir) {
    this.baseDir = baseDir;
    fs.mkdirSync(baseDir, { recursive: true });
  }

  path(name) {
    assertName(name);
    return path.join(this.baseDir, `${name}.json`);
  }

  read(name, fallback = { _schema: 1 }) {
    const file = this.path(name);
    try {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (error) {
      if (error.code !== 'ENOENT') console.error(`[store] ${name} 读取失败:`, error.message);
      return structuredClone(fallback);
    }
  }

  rotateBackups(file) {
    for (let index = 3; index >= 2; index -= 1) {
      const previous = `${file}.bak.${index - 1}`;
      const next = `${file}.bak.${index}`;
      if (fs.existsSync(previous)) fs.copyFileSync(previous, next);
    }
    if (fs.existsSync(file)) fs.copyFileSync(file, `${file}.bak.1`);
  }

  write(name, value) {
    const file = this.path(name);
    const temp = `${file}.${process.pid}.${Date.now()}.tmp`;
    const normalized = value && typeof value === 'object' && !Array.isArray(value)
      ? { _schema: value._schema || 1, ...value }
      : value;
    fs.writeFileSync(temp, JSON.stringify(normalized, null, 2), { encoding: 'utf8', mode: 0o600 });
    try {
      this.rotateBackups(file);
      fs.renameSync(temp, file);
    } catch (error) {
      try { fs.unlinkSync(temp); } catch (_) {}
      throw error;
    }
    return normalized;
  }

  update(name, fallback, updater) {
    const current = this.read(name, fallback);
    const next = updater(structuredClone(current));
    return this.write(name, next === undefined ? current : next);
  }

  appendAudit(entry) {
    const file = path.join(this.baseDir, 'audit.log');
    fs.appendFileSync(file, `${JSON.stringify({ ts: new Date().toISOString(), ...entry })}\n`, { encoding: 'utf8', mode: 0o600 });
  }
}

module.exports = { JsonStore, assertName };
