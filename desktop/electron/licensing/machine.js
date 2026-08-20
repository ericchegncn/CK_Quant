const crypto = require('crypto');
const os = require('os');
const { execFileSync } = require('child_process');

const PRODUCT_SALT = 'CK_QUANT_DESKTOP_MACHINE_V1';

function clean(value) {
  return String(value || '').trim().toUpperCase().replace(/\s+/g, ' ');
}

function readWindowsHardware() {
  const script = [
    "$ErrorActionPreference='SilentlyContinue'",
    '$values=@()',
    "$values+=(Get-CimInstance Win32_ComputerSystemProduct).UUID",
    "$values+=(Get-CimInstance Win32_BIOS).SerialNumber",
    "$values+=(Get-CimInstance Win32_BaseBoard).SerialNumber",
    "$values | Where-Object { $_ -and $_ -notmatch 'To be filled|Default string' } | ForEach-Object { $_.Trim() }",
  ].join(';');
  try {
    return execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], {
      encoding: 'utf8',
      windowsHide: true,
      timeout: 15000,
    }).split(/\r?\n/).map(clean).filter(Boolean);
  } catch (_) {
    return [];
  }
}

function collectMachineParts(overrides = {}) {
  if (Array.isArray(overrides.hardware) && overrides.hardware.length) {
    return overrides.hardware.map(clean).filter(Boolean);
  }
  const hardware = process.platform === 'win32' ? readWindowsHardware() : [];
  const identity = hardware.length ? hardware : [os.hostname()];
  return [process.platform, process.arch, ...identity].map(clean).filter(Boolean);
}

function formatMachineCode(hex) {
  return `CKQ-${hex.slice(0, 4)}-${hex.slice(4, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 24)}`;
}

function getMachineCode(overrides = {}) {
  const parts = collectMachineParts(overrides);
  const digest = crypto.createHash('sha256').update(`${PRODUCT_SALT}|${parts.join('|')}`).digest('hex').toUpperCase();
  return formatMachineCode(digest);
}

module.exports = { collectMachineParts, formatMachineCode, getMachineCode };
