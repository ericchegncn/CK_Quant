const crypto = require('crypto');

class ConfirmationManager {
  constructor({ send, timeoutMs = 30000 }) {
    this.send = send;
    this.timeoutMs = timeoutMs;
    this.pending = new Map();
  }

  request(payload) {
    const confirmationId = crypto.randomUUID();
    return new Promise((resolve) => {
      const timer = setTimeout(() => this.resolve(confirmationId, false), this.timeoutMs);
      this.pending.set(confirmationId, { resolve, timer });
      this.send('ai:requireConfirm', { ...payload, confirmationId, expiresInMs: this.timeoutMs, ts: new Date().toISOString() });
    });
  }

  resolve(confirmationId, approved) {
    const item = this.pending.get(confirmationId);
    if (!item) return false;
    clearTimeout(item.timer);
    this.pending.delete(confirmationId);
    item.resolve(Boolean(approved));
    return true;
  }

  close() {
    for (const id of [...this.pending.keys()]) this.resolve(id, false);
  }
}

module.exports = { ConfirmationManager };
