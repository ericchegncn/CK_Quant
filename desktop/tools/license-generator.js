#!/usr/bin/env node
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { issueRegistrationCode, verifyRegistrationCode } = require('../electron/licensing/codec');

const root = path.resolve(__dirname, '..');
const privateDir = path.join(root, 'private');
const privateKeyPath = path.join(privateDir, 'license-private-key.pem');
const publicKeyPath = path.join(root, 'resources', 'license-public-key.pem');

function arg(name) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 ? process.argv[index + 1] : null;
}

function initialize() {
  if (fs.existsSync(privateKeyPath)) throw new Error('授权私钥已存在，拒绝覆盖');
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  fs.mkdirSync(privateDir, { recursive: true });
  fs.mkdirSync(path.dirname(publicKeyPath), { recursive: true });
  fs.writeFileSync(privateKeyPath, privateKey.export({ type: 'pkcs8', format: 'pem' }), { mode: 0o600 });
  fs.writeFileSync(publicKeyPath, publicKey.export({ type: 'spki', format: 'pem' }));
  console.log('授权密钥初始化完成。请离线备份 desktop/private/license-private-key.pem，丢失后无法补发同体系注册码。');
}

function issue() {
  const machineCode = String(arg('machine') || '').trim().toUpperCase();
  if (!/^CKQ-(?:[A-F0-9]{4}-){5}[A-F0-9]{4}$/.test(machineCode)) throw new Error('请提供正确的 --machine 机器码');
  if (!fs.existsSync(privateKeyPath)) throw new Error('授权私钥不存在，请先运行 init');
  const code = issueRegistrationCode({
    licenseId: crypto.randomUUID(),
    machineCode,
    customer: arg('customer') || '',
    issuedAt: new Date().toISOString(),
  }, fs.readFileSync(privateKeyPath, 'utf8'));
  const checked = verifyRegistrationCode(code, fs.readFileSync(publicKeyPath, 'utf8'), machineCode);
  if (!checked.valid) throw new Error('内部验签失败，未签发注册码');
  console.log(code);
}

const command = process.argv[2];
try {
  if (command === 'init') initialize();
  else if (command === 'issue') issue();
  else {
    console.log('用法:');
    console.log('  node tools/license-generator.js init');
    console.log('  node tools/license-generator.js issue --machine CKQ-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX --customer 客户名称');
    process.exitCode = 1;
  }
} catch (error) {
  console.error(`失败: ${error.message}`);
  process.exitCode = 1;
}
