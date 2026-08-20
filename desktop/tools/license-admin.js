const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { issueRegistrationCode, verifyRegistrationCode } = require('../electron/licensing/codec');

const root = path.resolve(__dirname, '..');
const privateKeyPath = path.join(root, 'private', 'license-private-key.pem');
const publicKeyPath = path.join(root, 'resources', 'license-public-key.pem');

ipcMain.handle('admin:status', () => ({ ready: fs.existsSync(privateKeyPath) && fs.existsSync(publicKeyPath) }));
ipcMain.handle('admin:issue', (_event, { machineCode, customer }) => {
  const normalized = String(machineCode || '').trim().toUpperCase();
  if (!/^CKQ-(?:[A-F0-9]{4}-){5}[A-F0-9]{4}$/.test(normalized)) {
    return { ok: false, error: '机器码格式不正确，请完整复制客户机器码' };
  }
  if (!fs.existsSync(privateKeyPath)) return { ok: false, error: '授权私钥不存在' };
  const payload = {
    licenseId: crypto.randomUUID(),
    machineCode: normalized,
    customer: String(customer || '').trim(),
    issuedAt: new Date().toISOString(),
  };
  const code = issueRegistrationCode(payload, fs.readFileSync(privateKeyPath, 'utf8'));
  const result = verifyRegistrationCode(code, fs.readFileSync(publicKeyPath, 'utf8'), normalized);
  if (!result.valid) return { ok: false, error: '内部验签失败，未签发注册码' };
  const recordDir = path.join(root, 'license-codes');
  fs.mkdirSync(recordDir, { recursive: true });
  const record = { ...payload, licenseType: 'lifetime', registrationCode: code };
  fs.writeFileSync(path.join(recordDir, `${payload.licenseId}.json`), JSON.stringify(record, null, 2), { mode: 0o600 });
  return { ok: true, code, licenseId: payload.licenseId, issuedAt: payload.issuedAt };
});

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  const win = new BrowserWindow({
    width: 760,
    height: 680,
    minWidth: 680,
    minHeight: 600,
    title: 'CK Quant 注册码签发控制台',
    icon: path.join(root, 'build', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'license-admin-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, 'license-admin.html'));
});

app.on('window-all-closed', () => app.quit());
