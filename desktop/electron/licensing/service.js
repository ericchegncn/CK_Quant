const fs = require('fs');
const path = require('path');
const { getMachineCode } = require('./machine');
const { verifyRegistrationCode } = require('./codec');

function atomicWrite(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, content, { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(temp, file);
}

class LicenseService {
  constructor({ dataDir, publicKeyPath, safeStorage, machineCode } = {}) {
    this.dataDir = dataDir;
    this.publicKeyPath = publicKeyPath;
    this.safeStorage = safeStorage;
    this.machineCode = machineCode || getMachineCode();
    this.file = path.join(dataDir, 'license.json');
  }

  readCode() {
    try {
      const saved = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      if (saved.encryptedCode && this.safeStorage?.isEncryptionAvailable()) {
        return this.safeStorage.decryptString(Buffer.from(saved.encryptedCode, 'base64'));
      }
      return saved.registrationCode || '';
    } catch (_) {
      return '';
    }
  }

  verify(code = this.readCode()) {
    if (!code) return { valid: false, error: '尚未激活', machineCode: this.machineCode };
    try {
      const publicKey = fs.readFileSync(this.publicKeyPath, 'utf8');
      return { ...verifyRegistrationCode(code, publicKey, this.machineCode), machineCode: this.machineCode };
    } catch (_) {
      return { valid: false, error: '授权公钥缺失，请重新安装软件', machineCode: this.machineCode };
    }
  }

  activate(code) {
    const result = this.verify(code);
    if (!result.valid) return result;
    const data = { _schema: 1, activatedAt: new Date().toISOString() };
    if (this.safeStorage?.isEncryptionAvailable()) {
      data.encryptedCode = this.safeStorage.encryptString(String(code).replace(/\s+/g, '')).toString('base64');
    } else {
      data.registrationCode = String(code).replace(/\s+/g, '');
    }
    atomicWrite(this.file, JSON.stringify(data, null, 2));
    return this.verify();
  }

  remove() {
    try { fs.unlinkSync(this.file); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    return { ok: true };
  }
}

function registerLicenseHandlers(ipcMain, service, onStatusChanged = () => {}) {
  ipcMain.handle('license:status', () => service.verify());
  ipcMain.handle('license:machineCode', () => ({ ok: true, machineCode: service.machineCode }));
  ipcMain.handle('license:activate', (_event, { code }) => {
    const result = service.activate(code);
    onStatusChanged(result);
    return result;
  });
  ipcMain.handle('license:remove', () => {
    const result = service.remove();
    onStatusChanged({ valid: false });
    return result;
  });
}

module.exports = { LicenseService, atomicWrite, registerLicenseHandlers };
