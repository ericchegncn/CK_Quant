const crypto = require('crypto');

const PRODUCT = 'CK_QUANT_DESKTOP';
const PREFIX = 'CKQ1';

function b64urlEncode(value) {
  return Buffer.from(value).toString('base64url');
}

function b64urlDecode(value) {
  return Buffer.from(value, 'base64url');
}

function canonicalPayload(payload) {
  return JSON.stringify({
    product: payload.product,
    licenseId: payload.licenseId,
    machineCode: payload.machineCode,
    licenseType: payload.licenseType,
    edition: payload.edition,
    customer: payload.customer || '',
    issuedAt: payload.issuedAt,
    features: [...(payload.features || [])].sort(),
  });
}

function issueRegistrationCode(payload, privateKey) {
  const normalized = {
    product: PRODUCT,
    licenseId: payload.licenseId,
    machineCode: String(payload.machineCode || '').trim().toUpperCase(),
    licenseType: 'lifetime',
    edition: 'lifetime',
    customer: payload.customer || '',
    issuedAt: payload.issuedAt || new Date().toISOString(),
    features: payload.features || ['all'],
  };
  const body = canonicalPayload(normalized);
  const signature = crypto.sign(null, Buffer.from(body), privateKey);
  return `${PREFIX}.${b64urlEncode(body)}.${signature.toString('base64url')}`;
}

function verifyRegistrationCode(code, publicKey, expectedMachineCode) {
  try {
    const compact = String(code || '').replace(/\s+/g, '');
    const [prefix, bodyPart, signaturePart, extra] = compact.split('.');
    if (prefix !== PREFIX || !bodyPart || !signaturePart || extra) {
      return { valid: false, error: '注册码格式不正确' };
    }
    const body = b64urlDecode(bodyPart).toString('utf8');
    const payload = JSON.parse(body);
    if (canonicalPayload(payload) !== body) return { valid: false, error: '注册码内容已被修改' };
    if (!crypto.verify(null, Buffer.from(body), publicKey, b64urlDecode(signaturePart))) {
      return { valid: false, error: '注册码签名无效' };
    }
    if (payload.product !== PRODUCT || payload.licenseType !== 'lifetime') {
      return { valid: false, error: '注册码不适用于本产品' };
    }
    if (String(payload.machineCode).toUpperCase() !== String(expectedMachineCode).toUpperCase()) {
      return { valid: false, error: '注册码与本机机器码不匹配' };
    }
    return { valid: true, payload };
  } catch (_) {
    return { valid: false, error: '注册码无法解析' };
  }
}

module.exports = { PRODUCT, PREFIX, canonicalPayload, issueRegistrationCode, verifyRegistrationCode };
