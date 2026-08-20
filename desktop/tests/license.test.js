const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { getMachineCode } = require('../electron/licensing/machine');
const { issueRegistrationCode, verifyRegistrationCode } = require('../electron/licensing/codec');
const { LicenseService } = require('../electron/licensing/service');

test('machine code is stable for the same hardware parts', () => {
  const first = getMachineCode({ hardware: ['BOARD-1', 'BIOS-2'] });
  const second = getMachineCode({ hardware: ['BOARD-1', 'BIOS-2'] });
  assert.equal(first, second);
  assert.match(first, /^CKQ-(?:[A-F0-9]{4}-){5}[A-F0-9]{4}$/);
});

test('signed lifetime registration code verifies only on the bound machine', () => {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  const machineCode = getMachineCode({ hardware: ['CUSTOMER-PC'] });
  const code = issueRegistrationCode({ licenseId: 'license-1', machineCode, customer: 'Test' }, privateKey);
  const valid = verifyRegistrationCode(code, publicKey, machineCode);
  assert.equal(valid.valid, true);
  assert.equal(valid.payload.licenseType, 'lifetime');
  assert.equal(verifyRegistrationCode(code, publicKey, getMachineCode({ hardware: ['OTHER-PC'] })).valid, false);
});

test('tampered registration code is rejected', () => {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  const machineCode = getMachineCode({ hardware: ['CUSTOMER-PC'] });
  const code = issueRegistrationCode({ licenseId: 'license-2', machineCode }, privateKey);
  const parts = code.split('.');
  parts[1] = `${parts[1][0] === 'A' ? 'B' : 'A'}${parts[1].slice(1)}`;
  const tampered = parts.join('.');
  assert.equal(verifyRegistrationCode(tampered, publicKey, machineCode).valid, false);
});

test('license service persists and restores an encrypted activation', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'ckq-license-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519');
  const publicKeyPath = path.join(temp, 'public.pem');
  fs.writeFileSync(publicKeyPath, publicKey.export({ type: 'spki', format: 'pem' }));
  const safeStorage = {
    isEncryptionAvailable: () => true,
    encryptString: (value) => Buffer.from(`encrypted:${value}`),
    decryptString: (value) => value.toString().replace(/^encrypted:/, ''),
  };
  const machineCode = getMachineCode({ hardware: ['SERVICE-PC'] });
  const code = issueRegistrationCode({ licenseId: 'license-3', machineCode }, privateKey);
  const service = new LicenseService({ dataDir: temp, publicKeyPath, safeStorage, machineCode });
  assert.equal(service.activate(code).valid, true);
  assert.equal(service.verify().valid, true);
  assert.equal(JSON.parse(fs.readFileSync(path.join(temp, 'license.json'), 'utf8')).registrationCode, undefined);
});
